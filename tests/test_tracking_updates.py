import json

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from job_tracker.db import Application, ApplicationEvent, Job, Message, Review, Scan, Usage
from job_tracker.domain import Outcome, Stage
from job_tracker.email import register
from job_tracker.excel import export_search
from job_tracker.worker import Importer


@pytest.mark.parametrize(
    ("kind", "stage", "outcome"),
    [
        ("application", "Applied", "Active"),
        ("rejection", "Applied", "Rejected"),
        ("assessment", "Assessment", "Active"),
        ("interview", "Interview", "Active"),
        ("offer", "Offer", "Active"),
    ],
)
def test_unmatched_updates_create_records_without_inventing_applied_dates(
    tracker, kind, stage, outcome
):
    search = tracker.create_search("2026")
    register(tracker, "gmail", "candidate@example.org", "fake")
    account = tracker.accounts()[0]["id"]
    result = {
        "kind": kind,
        "probability": 0.99,
        "confidence": 0.99,
        "extraction": {
            "company": "OCLC",
            "role": "Software Engineer - Canada",
            "applied_on": "2026-09-20",
            "evidence": "Fictional evidence",
        },
    }
    importer = Importer(tracker, None)
    scan = importer.create_scan(search, {"start": "2026-09-01", "end": "2026-11-01"}, 1)
    with tracker.db.sessions.begin() as session:
        message = Message(
            account_id=account,
            provider_id="one",
            sender="jobs@example.org",
            subject="Update",
            body="Fictional update",
            received_at="2026-10-01T12:00:00Z",
            result_json=json.dumps(result),
        )
        session.add(message)
        session.flush()
        job = Job(message_id=message.id, search_id=search, scan_id=scan)
        session.add(job)
        session.flush()
        job_id = job.id
    importer.process(job_id, None)  # Cached results must not call AI again.
    app = tracker.applications(search)[0]
    assert (app["stage"], app["outcome"]) == (stage, outcome)
    assert app["applied_on"] == ("2026-09-20" if kind == "application" else "")
    assert not tracker.reviews(search)
    # An earlier confirmation fills a blank date without undoing the later rejection.
    with tracker.db.sessions.begin() as session:
        message = Message(
            account_id=account,
            provider_id="confirmation",
            sender="jobs@example.org",
            subject="Confirmation",
            body="Applied",
            received_at="2026-09-21T23:00:00-04:00",
        )
        session.add(message)
        session.flush()
        tracker.add_event(
            session,
            session.get(Application, app["id"]),
            message,
            {"kind": "application", "extraction": {}},
        )
    updated = tracker.applications(search)[0]
    assert updated["applied_on"] == ("2026-09-20" if kind == "application" else "2026-09-22")
    assert updated["outcome"] == outcome


def test_hide_import_preserves_records_and_billing(tracker):
    search = tracker.create_search("2026")
    app = tracker.save_application(search, {"company": "Company", "role": "Engineer"})
    importer = Importer(tracker, None)
    scan_id = importer.create_scan(search, {"start": "2026-09-01", "end": "2026-11-01"}, 1)
    with tracker.db.sessions.begin() as session:
        session.get(Scan, scan_id).state = "completed"
        # Usage remains linked to its email even after the history entry is hidden.
    register(tracker, "gmail", "candidate@example.org", "fake")
    with tracker.db.sessions.begin() as session:
        message = Message(
            account_id=tracker.accounts()[0]["id"],
            provider_id="one",
            sender="jobs@example.org",
            subject="Confirmation",
            body="Applied",
            received_at="2026-10-01T12:00:00Z",
        )
        session.add(message)
        session.flush()
        session.add(
            Usage(
                scan_id=scan_id,
                message_id=message.id,
                operation="classify",
                model="fake",
                input_tokens=1,
                output_tokens=0,
                cost=0.1,
            )
        )
    importer.hide_scan(scan_id, search)
    assert importer.scans(search) == []
    assert tracker.applications(search)[0]["id"] == app
    with tracker.db.sessions() as session:
        assert session.get(Scan, scan_id).hidden
        assert session.scalar(select(Usage.cost)) == 0.1
        assert session.scalar(select(ApplicationEvent.id)) is not None
    with pytest.raises(ValueError):
        importer.resume(scan_id, 1)


def test_search_edit_validates_before_changing_data(tracker):
    search = tracker.create_search("2026")
    tracker.edit_search(search, "  Co-op 2026  ", "2026-01-01", "2026-12-31", True)
    saved = tracker.searches()[0]
    assert saved["name"] == "Co-op 2026" and saved["archived"]
    with pytest.raises(ValueError):
        tracker.edit_search(search, "Oops", "2027-01-01", "2026-01-01", False)
    assert tracker.searches()[0] == saved


@pytest.mark.parametrize(
    "case", ["company", "role", "confidence", "probability", "other", "ambiguous", "conflicting-id"]
)
def test_unmatched_creation_keeps_uncertainty_and_conflicts_in_review(tracker, case):
    search = tracker.create_search("2026")
    register(tracker, "gmail", "candidate@example.org", "fake")
    result = {
        "kind": "rejection",
        "confidence": 0.99,
        "probability": 0.99,
        "extraction": {"company": "Company", "role": "Engineer", "evidence": "Rejected"},
    }
    if case in ("company", "role"):
        result["extraction"][case] = None
    elif case in ("confidence", "probability"):
        result[case] = 0.6
    elif case == "other":
        result["kind"] = "other"
    elif case == "ambiguous":
        for date in ("2026-08-01", "2026-09-01"):
            tracker.save_application(
                search, {"company": "Company", "role": "Engineer", "applied_on": date}
            )
    else:
        tracker.save_application(
            search, {"company": "Company", "role": "Engineer", "requisition_id": "OLD"}
        )
        result["extraction"]["requisition_id"] = "NEW"
    before = tracker.applications(search)
    importer = Importer(tracker, None)
    scan_id = importer.create_scan(search, {"start": "2026-09-01", "end": "2026-11-01"}, 1)
    job_id = importer.stage_message(tracker.accounts()[0], "one", scan_id, search)
    with tracker.db.sessions.begin() as session:
        message = session.get(Message, session.get(Job, job_id).message_id)
        message.body, message.state = "Rejected", "pending"
        message.received_at = "2026-10-01T00:00:00Z"
        message.result_json = json.dumps(result)
    importer.process(job_id, None)
    assert tracker.applications(search) == before
    assert len(tracker.reviews(search)) == 1


def test_excel_dropdowns_cover_existing_and_new_rows(tracker, tmp_path):
    search = tracker.create_search("2026")
    tracker.save_application(search, {"company": "Company", "role": "Engineer"})
    path = tmp_path / "export.xlsx"
    export_search(tracker, search, path)
    workbook = load_workbook(path)
    try:
        rules = list(workbook["Applications"].data_validations.dataValidation)
        assert [rule.formula1 for rule in rules] == [
            '"' + ",".join(item.value for item in enum) + '"' for enum in (Stage, Outcome)
        ]
        assert [str(rule.sqref) for rule in rules] == ["D2:D1048576", "E2:E1048576"]
        assert all(not rule.showDropDown and rule.showErrorMessage for rule in rules)
        assert workbook["Tasks"].data_validations.dataValidation[0].formula1 == '"TRUE,FALSE"'
    finally:
        workbook.close()


@pytest.mark.parametrize(
    ("confidence", "reason", "evidence", "replayed", "ambiguous_now"),
    [
        (0.99, "No exact application match.", "Rejected", True, False),
        (0.6, "No exact application match.", "Rejected", False, False),
        (0.99, "Multiple roles match this email.", "Rejected", False, False),
        (0.99, "No exact application match.", "Unsupported evidence", False, False),
        (0.99, "No exact application match.", "Rejected", False, True),
    ],
)
def test_rescan_applies_clear_old_reviews_without_another_ai_call(
    tracker, confidence, reason, evidence, replayed, ambiguous_now
):
    search = tracker.create_search("2026")
    register(tracker, "gmail", "candidate@example.org", "fake")
    account = tracker.accounts()[0]
    importer = Importer(tracker, None)
    plan = {"start": "2026-09-01", "end": "2026-11-01"}
    old_scan = importer.create_scan(search, plan, 1)
    job_id = importer.stage_message(account, "old-review", old_scan, search)
    with tracker.db.sessions.begin() as session:
        job = session.get(Job, job_id)
        job.state = "review"
        message = session.get(Message, job.message_id)
        message.state, message.body = "processed", "Rejected"
        message.received_at = "2026-10-01T12:00:00Z"
        result = {
            "kind": "rejection",
            "confidence": confidence,
            "probability": 0.99,
            "extraction": {"company": "Company", "role": "Engineer", "evidence": evidence},
        }
        message.result_json = json.dumps(result)
        session.add(
            Review(job_id=job_id, search_id=search, reason=reason, proposed_json=json.dumps(result))
        )
    if ambiguous_now:
        for date in ("2026-08-01", "2026-09-01"):
            tracker.save_application(
                search, {"company": "Company", "role": "Engineer", "applied_on": date}
            )
    existing_count = len(tracker.applications(search))
    new_scan = importer.create_scan(search, plan, 1)
    assert importer.stage_message(account, "old-review", new_scan, search) == job_id
    importer.process(job_id, None)  # Any attempt to classify/extract would fail this test.
    assert len(tracker.applications(search)) == existing_count + int(replayed)
    assert len(tracker.reviews(search)) == int(not replayed)
    if ambiguous_now:
        assert tracker.reviews(search)[0]["reason"] == "Multiple roles match this email."
    if replayed:
        assert tracker.applications(search)[0]["outcome"] == "Rejected"
        assert tracker.applications(search)[0]["applied_on"] == ""
        assert importer.stage_message(account, "old-review", new_scan, search) == job_id
        importer.process(job_id, None)
        assert len(tracker.applications(search)) == 1
    with tracker.db.sessions() as session:
        assert session.scalar(select(Usage.id)) is None
