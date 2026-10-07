import json

import pytest
from sqlalchemy import select

from job_tracker.credentials import Credentials
from job_tracker.db import Application, Job, Message, Usage
from job_tracker.email import Email, normalize, register
from job_tracker.worker import Importer, match_application


class FakeAnalyzer:
    calls = 0
    fail = False

    def __init__(self, key):
        pass

    def classify(self, message, bill):
        type(self).calls += 1
        receipt = bill("classify", "gpt-6-luna", 0.01)
        if self.fail:
            raise RuntimeError("Private email / secret credential must not be displayed")
        bill("settle", receipt, {"input_tokens": 1000, "output_tokens": 0})
        return {
            "probability": 0.99,
            "kind": "application",
            "confidence": 0.99,
            "prompt_version": 1,
            "model": "gpt-6-luna",
        }

    def extract(self, message, bill):
        receipt = bill("extract", "gpt-5.4-mini", 0.02)
        bill("settle", receipt, {"input_tokens": 1000, "output_tokens": 100})
        return {
            "company": "Example Company",
            "role": "Developer",
            "requisition_id": "REQ-1",
            "applied_on": None,
            "deadline_at": None,
            "interview_at": None,
            "evidence": "We received your application.",
        }

    def close(self):
        pass


class FakeMailbox:
    def __init__(self, account, vault):
        pass

    def list_ids(self, start, end, cancelled=lambda: False):
        return ["message-1"]

    def get(self, provider_id):
        return Email(
            provider_id,
            "thread-1",
            "jobs@example.org",
            "Application received",
            "We received your application.",
            "2026-10-01T12:00:00+00:00",
        )


@pytest.fixture
def importer(tracker):
    FakeAnalyzer.calls, FakeAnalyzer.fail = 0, False
    vault = Credentials()
    vault.save("mailbox", "fake-token", persist=False)
    register(tracker, "gmail", "candidate@example.org", "mailbox")
    return Importer(tracker, vault, FakeAnalyzer, FakeMailbox)


def test_scan_deduplicates_and_reuses_ai(importer, tracker):
    search = tracker.create_search("2026")
    plan = importer.preview("2026-09-01T00:00:00Z", "2026-11-01T00:00:00Z")
    scan = importer.create_scan(search, plan, 1)
    assert importer.run(scan, plan)["state"] == "completed"
    assert FakeAnalyzer.calls == 1
    assert len(tracker.applications(search)) == 1
    assert tracker.applications(search)[0]["applied_on"] == ""  # Do not infer from arrival.
    second_plan = importer.preview(plan["start"], plan["end"])
    assert second_plan["estimate"]["count"] == 0
    second = importer.create_scan(search, second_plan, 1)
    importer.run(second, second_plan)
    assert FakeAnalyzer.calls == 1
    assert len(tracker.events(tracker.applications(search)[0]["id"])) == 1


def test_budget_stops_before_request_and_scan_resumes(importer, tracker):
    search = tracker.create_search("2026")
    plan = importer.preview("2026-09-01T00:00:00Z", "2026-11-01T00:00:00Z")
    scan = importer.create_scan(search, plan, 0.001)
    result = importer.run(scan, plan)
    assert result["state"] == "paused"
    assert result["spent"] == 0
    assert FakeAnalyzer.calls == 1  # Called the adapter, but reservation blocked network dispatch.
    assert not tracker.applications(search)
    assert importer.resume(scan, 1)["state"] == "completed"


def test_failed_request_retains_reservation_and_sanitizes_error(importer, tracker):
    FakeAnalyzer.fail = True
    search = tracker.create_search("2026")
    plan = importer.preview("2026-09-01T00:00:00Z", "2026-11-01T00:00:00Z")
    scan = importer.create_scan(search, plan, 1)
    result = importer.run(scan, plan)
    assert result["state"] == "paused"
    assert result["spent"] == pytest.approx(0.01)
    with tracker.db.sessions() as session:
        job = session.scalar(select(Job))
        assert "secret" not in job.error
        assert session.scalar(select(Usage)).input_tokens == 0
    assert not tracker.applications(search)


def test_late_email_matches_original_search_and_is_idempotent(importer, tracker):
    old, current = tracker.create_search("2024"), tracker.create_search("2026")
    app_id = tracker.save_application(
        old, {"company": "Example Company", "role": "Developer", "requisition_id": "REQ-1"}
    )
    with tracker.db.sessions.begin() as session:
        app = session.get(Application, app_id)
        app.status_at = "2024-12-01T12:00:00+00:00"
        message = Message(
            account_id=tracker.accounts()[0]["id"],
            provider_id="late",
            thread_id="t",
            sender="jobs@example.org",
            subject="Update",
            body="Rejected",
            received_at="2025-01-10T12:00:00+00:00",
        )
        session.add(message)
        session.flush()
        extraction = {
            "company": "Example Company",
            "role": "Developer",
            "requisition_id": "REQ-1",
            "evidence": "Rejected",
        }
        app, reason = match_application(session, message, extraction, current)
        assert app.id == app_id and not reason
        result = {"kind": "rejection", "extraction": extraction}
        tracker.add_event(session, app, message, result)
        tracker.add_event(session, app, message, result)
    assert tracker.applications(old)[0]["outcome"] == "Rejected"
    assert not tracker.applications(current)
    assert len(tracker.events(app_id)) == 2  # Manual creation plus exactly one email event.


def test_matching_refuses_ambiguous_roles(tracker):
    search = tracker.create_search("2026")
    for requisition in ("ONE", "TWO"):
        tracker.save_application(
            search, {"company": "Company", "role": "Developer", "requisition_id": requisition}
        )
    with tracker.db.sessions() as session:
        message = Message(
            account_id=1,
            provider_id="m",
            sender="a",
            subject="b",
            body="c",
            thread_id="",
            received_at="2026-10-01T00:00:00Z",
        )
        app, reason = match_application(
            session, message, {"company": "Company", "role": "Developer"}, search
        )
        assert app is None and reason


def test_normalization_removes_html_and_quoted_replies():
    assert (
        normalize("<style>hidden</style><p>Interview</p><script>bad()</script>", True)
        == "Interview"
    )
    assert normalize("Interview\nOn Monday recruiter wrote:\nRejected") == "Interview"
    assert len(normalize("x" * 20000)) == 16000


def test_preview_counts_partial_cache_as_billable(importer, tracker):
    account = tracker.accounts()[0]
    with tracker.db.sessions.begin() as session:
        session.add(
            Message(
                account_id=account["id"],
                **vars(FakeMailbox(account, None).get("message-1")),
                result_json=json.dumps({"kind": "application", "probability": 0.99}),
            )
        )
    assert (
        importer.preview("2026-09-01T00:00:00Z", "2026-11-01T00:00:00Z")["estimate"]["count"] == 1
    )


def test_manual_status_is_preserved_against_new_email(importer, tracker):
    search = tracker.create_search("2026")
    app_id = tracker.save_application(search, {"company": "Company", "role": "Developer"})
    tracker.save_application(
        search, {"company": "Company", "role": "Developer", "stage": "Offer"}, app_id
    )
    with tracker.db.sessions.begin() as session:
        app = session.get(Application, app_id)
        message = Message(
            account_id=tracker.accounts()[0]["id"],
            provider_id="new",
            sender="a",
            subject="s",
            body="Rejected",
            received_at="2027-01-01T00:00:00+00:00",
        )
        session.add(message)
        session.flush()
        tracker.add_event(session, app, message, {"kind": "rejection", "extraction": {}})
    assert tracker.applications(search)[0]["stage"] == "Offer"
    assert tracker.applications(search)[0]["outcome"] == "Active"
