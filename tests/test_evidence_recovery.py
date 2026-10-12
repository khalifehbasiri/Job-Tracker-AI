import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from job_tracker.db import ApplicationEvent, Job, Message, Review, Usage
from job_tracker.email import register
from job_tracker.errors import ReviewRequired
from job_tracker.evidence import EVIDENCE_REVIEW, recover_event_evidence, source_excerpt
from job_tracker.worker import Importer


@pytest.mark.parametrize(
    ("body", "excerpt"),
    [
        ("Received your\r\n\t application.", "Received your application."),
        ("Thank&nbsp;you for your application.", "Thank you for your application."),
        ("We\u2019ve received\u00a0your application.", "We've received your application."),
        ("Research &amp; Development", "Research & Development"),
    ],
)
def test_formatting_equivalent_evidence_preserves_exact_source(body, excerpt):
    assert source_excerpt(body, excerpt) == body


@pytest.mark.parametrize("excerpt", ["", "Application received", "We ... application."])
def test_evidence_cannot_be_paraphrased_or_joined(excerpt):
    assert source_excerpt("We received your application.", excerpt) == ""


def proposal(kind="application", confidence=1.0):
    return {
        "probability": 1.0,
        "confidence": confidence,
        "kind": kind,
        "review_reason": EVIDENCE_REVIEW,
        "extraction": {
            "company": "Company",
            "role": "Engineer",
            "requisition_id": None,
            "evidence": "",
            "applied_on": "2026-09-01",
            "deadline_at": "2026-11-01T12:00:00Z",
            "interview_at": None,
        },
    }


@pytest.mark.parametrize(
    ("kind", "body"),
    [
        ("application", "Thank you for successfully completing your application."),
        ("rejection", "We have not selected you to move forward for this role."),
        ("assessment", "Please complete your technical assessment."),
        ("interview", "We invite you to an interview."),
        ("offer", "We are pleased to offer you the position."),
    ],
)
def test_local_recovery_supports_literal_events_and_drops_unproven_dates(kind, body):
    message = SimpleNamespace(subject="Company / Engineer", body=body)
    original = proposal(kind)
    repaired = recover_event_evidence(message, original)
    assert repaired is not None
    assert repaired["extraction"]["evidence"] in body
    assert repaired["evidence_source"] == "local_explicit_event"
    assert "review_reason" not in repaired
    for field in ("applied_on", "deadline_at", "interview_at"):
        assert repaired["extraction"][field] is None
    assert original["extraction"]["evidence"] == ""


@pytest.mark.parametrize(
    "body",
    [
        "Company / Engineer: roles you might like.",
        "Company / Engineer: Hello.\nOn Monday someone\nwrote:\nWe received your application.",
        "Company / Engineer: Hello.\n-----Original Message-----\nWe received your application.",
        "Company / Engineer: Hello.\n> We received your application.",
        "Company / Engineer: Hello.\nView similar jobs\nWe received your application.",
        "We received your application for Architect at Other Company.",
        "Company / Engineer: We received your application. "
        "We will not be moving forward with your application.",
    ],
)
def test_local_recovery_rejects_promotions_quotes_and_unsupported_identity(body):
    assert recover_event_evidence(SimpleNamespace(subject="Update", body=body), proposal()) is None


def seed_review(tracker, result, body, reason=EVIDENCE_REVIEW, thread=""):
    search = tracker.create_search("2026")
    register(tracker, "gmail", "candidate@example.org", "fake")
    importer = Importer(tracker, None)
    scan = importer.create_scan(search, {"start": "2026-09-01", "end": "2026-11-01"}, 1)
    job_id = importer.stage_message(tracker.accounts()[0], "one", scan, search)
    with tracker.db.sessions.begin() as session:
        job = session.get(Job, job_id)
        job.state = "review"
        message = session.get(Message, job.message_id)
        message.state, message.body, message.subject = "processed", body, "Company / Engineer"
        message.thread_id = thread
        message.received_at = "2026-10-01T12:00:00Z"
        message.result_json = json.dumps(result)
        session.add(
            Review(job_id=job_id, search_id=search, proposed_json=json.dumps(result), reason=reason)
        )
    return importer, search, job_id


def test_backlog_recheck_uses_cached_text_and_is_idempotent(tracker):
    importer, search, job_id = seed_review(tracker, proposal(), "We received your application.")
    assert importer.reprocess_reviews(search) == {"applied": 1, "remaining": 0}
    app = tracker.applications(search)[0]
    assert app["applied_on"] == "2026-10-01"  # Rejected extraction's date wasn't retained.
    assert not tracker.tasks(search)
    assert importer.reprocess_reviews(search) == {"applied": 0, "remaining": 0}
    with tracker.db.sessions() as session:
        assert session.get(Job, job_id).state == "done"
        assert session.scalar(select(Review.state)) == "accepted"
        assert len(list(session.scalars(select(ApplicationEvent)))) == 1
        assert session.scalar(select(Usage.id)) is None


@pytest.mark.parametrize("case", ["low", "missing-role", "conflict", "ambiguous", "refusal"])
def test_backlog_recheck_preserves_remaining_review_guards(tracker, case):
    result = proposal()
    if case == "low":
        result["confidence"] = 0.89
    elif case == "missing-role":
        result["extraction"]["role"] = None
    elif case == "refusal":
        result["review_reason"] = "The classifier declined this email. Review it manually."
    importer, search, job_id = seed_review(tracker, result, "We received your application.")
    if case == "conflict":
        tracker.save_application(
            search, {"company": "Company", "role": "Engineer", "requisition_id": "OLD"}
        )
        with tracker.db.sessions.begin() as session:
            message = session.get(Message, session.get(Job, job_id).message_id)
            message.body += " Requisition NEW."
            result["extraction"]["requisition_id"] = "NEW"
            message.result_json = json.dumps(result)
    elif case == "ambiguous":
        for date in ("2026-08-01", "2026-09-01"):
            tracker.save_application(
                search, {"company": "Company", "role": "Engineer", "applied_on": date}
            )
    before = tracker.applications(search)
    assert importer.reprocess_reviews(search) == {"applied": 0, "remaining": 1}
    assert tracker.applications(search) == before


def test_recheck_revisits_earlier_email_when_later_email_identifies_the_thread(tracker):
    result = proposal()
    result["extraction"]["role"] = None
    importer, search, job_id = seed_review(
        tracker, result, "Company: We received your application.", thread="shared"
    )
    with tracker.db.sessions.begin() as session:
        first_job = session.get(Job, job_id)
        first = session.get(Message, first_job.message_id)
        rejection = proposal("rejection")
        second = Message(
            account_id=first.account_id,
            provider_id="later",
            thread_id="shared",
            subject="Company / Engineer",
            sender="jobs@example.org",
            body="We will not be moving forward with your application.",
            received_at="2026-10-02T12:00:00Z",
            state="processed",
            result_json=json.dumps(rejection),
        )
        session.add(second)
        session.flush()
        job = Job(message_id=second.id, search_id=search, scan_id=first_job.scan_id, state="review")
        session.add(job)
        session.flush()
        session.add(
            Review(
                job_id=job.id,
                search_id=search,
                reason=EVIDENCE_REVIEW,
                proposed_json=json.dumps(rejection),
            )
        )
    assert importer.reprocess_reviews(search) == {"applied": 2, "remaining": 0}
    assert importer.reprocess_reviews(search) == {"applied": 0, "remaining": 0}
    app = tracker.applications(search)[0]
    assert app["outcome"] == "Rejected"
    assert app["applied_on"] == "2026-10-01"
    assert len(tracker.events(app["id"])) == 2


def test_new_extraction_failure_can_recover_without_paid_retry(tracker):
    result = proposal("rejection")
    result.pop("review_reason")
    result.pop("extraction")
    importer, search, job_id = seed_review(
        tracker, result, "We will not be moving forward with your application."
    )
    with tracker.db.sessions.begin() as session:
        session.get(Job, job_id).state = "pending"
    calls = []

    class Analyzer:
        def extract(self, message, bill):
            calls.append(message.id)
            raise ReviewRequired(EVIDENCE_REVIEW, proposal()["extraction"])

    importer.process(job_id, Analyzer())
    assert len(calls) == 1
    assert tracker.applications(search)[0]["outcome"] == "Rejected"
    assert not tracker.reviews(search)


def test_recheck_button_runs_in_background_and_refreshes_review_count(qapp, qtbot, tracker):
    from job_tracker.credentials import Credentials
    from job_tracker.ui.bridge import Bridge

    _, search, _ = seed_review(tracker, proposal(), "We received your application.")
    tracker.set_setting("selected_search", str(search))
    vault = Credentials()
    vault.get = lambda _name: ""
    bridge = Bridge(tracker, vault, onboarding=False)
    bridge.timer.stop()
    assert len(bridge.reviews) == 1
    bridge.reprocessReviews()
    qtbot.waitUntil(lambda: not bridge.busy)
    qtbot.waitUntil(lambda: len(bridge.reviews) == 0)
    assert "Automatically applied 1 saved emails" in bridge.message
    assert bridge.scans[0]["review_count"] == 0
    assert bridge.scans[0]["processed"] == 1
    bridge.stop()
