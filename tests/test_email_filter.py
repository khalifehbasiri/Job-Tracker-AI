import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from job_tracker.db import Application, Job, Message, Review, Usage
from job_tracker.email import register
from job_tracker.errors import ReviewRequired
from job_tracker.evidence import EVIDENCE_REVIEW
from job_tracker.excel import export_search
from job_tracker.worker import Importer


@pytest.fixture
def inbox(tracker):
    search = tracker.create_search("2026")
    register(tracker, "gmail", "candidate@example.org", "fake")
    importer = Importer(tracker, None)
    scan = importer.create_scan(search, {"start": "2026-10-01", "end": "2026-11-01"}, 1)
    return importer, search, scan


def email(inbox, seconds=0, kind="application", company="Company", role="Engineer", **options):
    importer, search, scan = inbox
    body = options.pop("body", "We received your application.")
    received = options.pop(
        "received", (datetime(2026, 10, 1, 12, tzinfo=UTC) + timedelta(seconds=seconds)).isoformat()
    )
    result = {
        "kind": kind,
        "probability": 0.99,
        "confidence": options.pop("confidence", 0.99),
        "extraction": {"company": company, "role": role, "evidence": body, **options.pop("ex", {})},
    }
    if options.get("review_reason"):
        result["review_reason"] = options["review_reason"]
    with importer.tracker.db.sessions.begin() as session:
        message = Message(
            account_id=options.get("account", importer.tracker.accounts()[0]["id"]),
            provider_id=options.pop("provider", str(seconds)),
            thread_id=options.get("thread", ""),
            sender="jobs@example.org",
            subject=f"{company or ''} / {role or ''}",
            body=body,
            received_at=received,
            result_json=json.dumps(result),
        )
        session.add(message)
        session.flush()
        job = Job(message_id=message.id, search_id=search, scan_id=scan)
        session.add(job)
        session.flush()
        job_id = job.id
    return job_id


def job(inbox, job_id):
    with inbox[0].tracker.db.sessions() as session:
        return session.get(Job, job_id)


@pytest.mark.parametrize(("seconds", "filtered"), [(1199, True), (1200, True), (1201, False)])
def test_fixed_window_boundary_and_retained_source_dates(tracker, inbox, seconds, filtered):
    importer, search, scan = inbox
    original = email(inbox)
    importer.process(original, None)
    repeat = email(inbox, seconds)
    importer.process(repeat, None)
    app = tracker.applications(search)[0]
    assert bool(job(inbox, repeat).filtered_into_message_id) == filtered
    assert len(tracker.events(app["id"])) == (1 if filtered else 2)
    assert app["applied_on"] == "2026-10-01"
    assert app["first_email_at"] == "2026-10-01T12:00:00+00:00"
    assert (
        app["last_email_at"]
        == (datetime(2026, 10, 1, 12, tzinfo=UTC) + timedelta(seconds=seconds)).isoformat()
    )
    if filtered:
        assert app["status_at"] == app["first_email_at"]
        with tracker.db.sessions() as session:
            assert (
                job(inbox, repeat).filtered_into_message_id == session.get(Job, original).message_id
            )
            assert (
                session.get(Message, job(inbox, repeat).message_id).body
                == "We received your application."
            )
    assert importer.scans(search)[0]["filtered"] == int(filtered)
    importer.process(repeat, None)  # A resumed scan must not duplicate the event or dates.
    assert tracker.applications(search)[0] == app


def test_filtered_siblings_do_not_extend_window(tracker, inbox):
    importer, search, _ = inbox
    ids = [email(inbox, minute * 60) for minute in (0, 19, 38)]
    for identifier in ids:
        importer.process(identifier, None)
    assert [bool(job(inbox, identifier).filtered_into_message_id) for identifier in ids] == [
        False,
        True,
        False,
    ]
    assert len(tracker.events(tracker.applications(search)[0]["id"])) == 2


@pytest.mark.parametrize("kind", ["rejection", "assessment", "interview", "offer"])
def test_status_changes_survive_close_together_emails(tracker, inbox, kind):
    importer, search, _ = inbox
    importer.process(email(inbox), None)
    next_email = email(inbox, 60, kind=kind, body=f"Your {kind} update.")
    importer.process(next_email, None)
    assert not job(inbox, next_email).filtered_into_message_id
    app = tracker.applications(search)[0]
    assert [e["kind"] for e in tracker.events(app["id"])] == [kind, "application"]
    assert app["last_email_at"] == "2026-10-01T12:01:00+00:00"


@pytest.mark.parametrize("case", ["deadline", "interview", "applied-date", "action", "low-score"])
def test_confirmation_with_new_information_is_not_filtered(tracker, inbox, case):
    importer, search, _ = inbox
    importer.process(email(inbox), None)
    options = {
        "deadline": {"ex": {"deadline_at": "2026-10-03T12:00:00Z"}},
        "interview": {"ex": {"interview_at": "2026-10-03T12:00:00Z"}},
        "applied-date": {"ex": {"applied_on": "2026-09-30"}},
        "action": {"body": "We received your application. Please verify your email address."},
        "low-score": {"confidence": 0.89},
    }[case]
    followup = email(inbox, 60, **options)
    importer.process(followup, None)
    assert not job(inbox, followup).filtered_into_message_id
    assert job(inbox, followup).state == ("review" if case == "low-score" else "done")
    assert tracker.applications(search)[0]["applied_on"] == "2026-10-01"
    if case in ("deadline", "interview"):
        assert len(tracker.tasks(search)) == 1


@pytest.mark.parametrize("case", ["role", "company", "id", "account", "search", "unsupported"])
def test_distinct_or_unsupported_identities_are_not_filtered(tracker, inbox, case):
    importer, search, scan = inbox
    importer.process(
        email(inbox, ex={"requisition_id": "OLD"}, body="We received your application. OLD"), None
    )
    options = {
        "role": {"role": "Architect"},
        "company": {"company": "Other"},
        "id": {"ex": {"requisition_id": "NEW"}, "body": "We received your application. NEW"},
        "unsupported": {"ex": {"requisition_id": "invented"}},
    }.get(case, {})
    if case == "account":
        register(tracker, "gmail", "another@example.org", "fake2")
        options["account"] = tracker.accounts()[1]["id"]
    if case == "search":
        search = tracker.create_search("Other search")
        scan = importer.create_scan(search, {"start": "2026-10-01", "end": "2026-11-01"}, 1)
    followup = email((importer, search, scan), 60, **options)
    importer.process(followup, None)
    assert not job(inbox, followup).filtered_into_message_id


def test_saved_routine_notice_before_confirmation_is_filtered_without_ai(tracker, inbox):
    importer, search, _ = inbox
    notice = email(
        inbox,
        -60,
        kind="other",
        role=None,
        body="Company email preferences.",
        review_reason=EVIDENCE_REVIEW,
    )
    importer.process(notice, None)
    assert job(inbox, notice).state == "review"
    importer.process(email(inbox), None)
    assert importer.reprocess_reviews(search) == {"applied": 0, "filtered": 1, "remaining": 0}
    app = tracker.applications(search)[0]
    assert len(tracker.events(app["id"])) == 1
    assert app["first_email_at"] == "2026-10-01T11:59:00+00:00"
    assert app["applied_on"] == "2026-10-01"
    with tracker.db.sessions() as session:
        assert session.scalar(select(Review.state)) == "ignored"
        assert session.scalar(select(Usage.id)) is None
    assert importer.reprocess_reviews(search) == {"applied": 0, "remaining": 0}


def test_import_rechecks_earlier_notice_and_resumes_without_reprocessing(tracker, inbox):
    importer, search, scan = inbox
    notice = email(
        inbox,
        -60,
        kind="other",
        role=None,
        body="Company email preferences.",
        review_reason=EVIDENCE_REVIEW,
    )
    confirmation = email(inbox)
    importer.vault = SimpleNamespace(get=lambda _name: "fake")
    importer.analyzer_factory = lambda _key: None  # All results are already cached.
    plan = {
        "start": "2026-10-01",
        "end": "2026-10-02",
        "candidates": {str(tracker.accounts()[0]["id"]): ["-60", "0"]},
    }
    assert importer.run(scan, plan)["state"] == "completed"
    assert job(inbox, notice).filtered_into_message_id == job(inbox, confirmation).message_id
    assert not tracker.reviews(search)
    assert len(tracker.events(tracker.applications(search)[0]["id"])) == 1
    assert importer.scans(search)[0]["filtered"] == 1
    assert importer.scans(search)[0]["processed"] == 2
    before = tracker.applications(search)
    assert importer.resume(scan, 1)["state"] == "completed"
    assert tracker.applications(search) == before


@pytest.mark.parametrize(
    "case", ["required-action", "ambiguous", "unknown", "far", "refusal", "conflict", "footer"]
)
def test_routine_notice_needs_unambiguous_safe_identity(tracker, inbox, case):
    importer, _, _ = inbox
    importer.process(email(inbox), None)
    if case == "ambiguous":
        importer.process(email(inbox, 1, role="Architect"), None)
    body = "Company email preferences."
    if case == "required-action":
        body += " Please complete your application."
    elif case == "footer":
        body = "Your application has a new update.\n\nCompany privacy policy."
    options = {"kind": "other", "role": None, "body": body}
    if case == "unknown":
        options["company"] = None
    if case == "refusal":
        options["review_reason"] = "The classifier declined this email. Review it manually."
    if case == "conflict":
        options.update(thread="same", ex={"requisition_id": "NEW"}, body=body + " NEW")
        # Establish a strong thread identity with a conflicting requisition.
        with tracker.db.sessions.begin() as session:
            session.get(Message, 1).thread_id = "same"
            session.scalar(select(Application)).requisition_id = "OLD"
    notice = email(inbox, 1201 if case == "far" else 60, **options)
    importer.process(notice, None)
    assert job(inbox, notice).state == "review"
    assert not job(inbox, notice).filtered_into_message_id


def test_fresh_extraction_evidence_failure_can_filter_explicit_safe_notice(tracker, inbox):
    importer, search, _ = inbox
    importer.process(email(inbox), None)
    notice = email(inbox, 60, kind="other", role=None, body="Company privacy notice.")
    with tracker.db.sessions.begin() as session:
        message = session.get(Message, session.get(Job, notice).message_id)
        result = json.loads(message.result_json)
        extraction = result.pop("extraction")
        message.result_json = json.dumps(result)

    class Extractor:
        def extract(self, message, bill):
            raise ReviewRequired(EVIDENCE_REVIEW, extraction)

    importer.process(notice, Extractor())
    assert job(inbox, notice).filtered_into_message_id
    assert not tracker.reviews(search)


def test_received_dates_use_utc_and_preserve_manual_applied_date(tracker, inbox, tmp_path):
    importer, search, _ = inbox
    app_id = tracker.save_application(
        search, {"company": "Company", "role": "Engineer", "applied_on": "2026-09-15"}
    )
    importer.process(email(inbox, kind="rejection", received="2026-10-01T23:50:00-04:00"), None)
    importer.process(email(inbox, 60, received="2026-10-01T10:00:00+02:00"), None)
    app = tracker.applications(search)[0]
    assert app["applied_on"] == "2026-09-15"
    assert app["first_email_at"] == "2026-10-01T08:00:00+00:00"
    assert app["last_email_at"] == "2026-10-02T03:50:00+00:00"
    rejection = next(e for e in tracker.events(app_id) if e["kind"] == "rejection")
    assert rejection["effective_at"] == app["last_email_at"]
    path = tmp_path / "dates.xlsx"
    export_search(tracker, search, path)
    workbook = load_workbook(path)
    assert workbook["Applications"]["H2"].value == app["first_email_at"]
    assert workbook["Applications"]["I2"].value == app["last_email_at"]
    workbook.close()
