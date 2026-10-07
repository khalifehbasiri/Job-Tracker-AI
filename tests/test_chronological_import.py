import json

from sqlalchemy import select
from test_scan_recovery import setup_importer
from test_worker import FakeAnalyzer, FakeMailbox

from job_tracker.db import Job, Message
from job_tracker.email import register
from job_tracker.errors import ReviewRequired


def test_imports_oldest_first_across_accounts_and_resume(tracker):
    processed = []
    dates = {
        "new": "2026-10-03T00:00:00+00:00",
        "middle": "2026-10-02T00:00:00+00:00",
        "old": "2026-10-01T00:00:00+00:00",
    }

    class Mailbox(FakeMailbox):
        def __init__(self, account, vault):
            self.account = account

        def list_ids(self, *args):
            return ["new", "old"] if self.account["provider"] == "gmail" else ["middle"]

        def received_at(self, provider_id):
            return dates[provider_id]

        def get(self, provider_id):
            message = super().get(provider_id)
            message.received_at = dates[provider_id]
            return message

    class Analyzer(FakeAnalyzer):
        def classify(self, message, bill):
            processed.append(message.provider_id)
            result = super().classify(message, bill)
            if message.provider_id == "old":
                importer.cancelled.set()
            return result

    importer, search = setup_importer(tracker, Mailbox, Analyzer)
    register(tracker, "outlook", "other@example.org", "mailbox")
    plan = importer.preview("2026-09-01T00:00:00Z", "2026-11-01T00:00:00Z")
    scan = importer.create_scan(search, plan, 1)
    # A cached newer message must not jump ahead of older undownloaded messages.
    job = importer.stage_message(tracker.accounts()[0], "new", scan, search)
    with tracker.db.sessions.begin() as session:
        row = session.get(Message, session.get(Job, job).message_id)
        for key, value in vars(Mailbox(tracker.accounts()[0], None).get("new")).items():
            setattr(row, key, value)
        row.state = "pending"
    assert importer.run(scan, plan)["state"] == "paused"
    assert processed == ["old"]
    importer.cancelled.clear()
    assert importer.resume(scan, 1)["state"] == "completed"
    assert processed == ["old", "middle", "new"]


def test_invalid_extraction_goes_to_review_and_is_not_charged_again(tracker):
    class Analyzer(FakeAnalyzer):
        extracts = 0

        def extract(self, message, bill):
            type(self).extracts += 1
            raise ReviewRequired("AI evidence did not match the email text.")

    importer, search = setup_importer(tracker, analyzer=Analyzer)
    plan = importer.preview("2026-09-01T00:00:00Z", "2026-11-01T00:00:00Z")
    scan = importer.create_scan(search, plan, 1)
    assert importer.run(scan, plan)["state"] == "completed"
    assert len(tracker.reviews(search)) == 1
    assert not tracker.applications(search)
    assert importer.scans(search)[0]["failed"] == 0
    assert importer.resume(scan, 1)["state"] == "completed"
    assert Analyzer.extracts == 1


def test_existing_invalid_extractions_recover_without_another_api_call(tracker):
    importer, search = setup_importer(tracker)
    plan = importer.preview("2026-09-01T00:00:00Z", "2026-11-01T00:00:00Z")
    scan = importer.create_scan(search, plan, 1)
    job_id = importer.stage_message(tracker.accounts()[0], "message-1", scan, search)
    with tracker.db.sessions.begin() as session:
        job = session.get(Job, job_id)
        job.state = "error"
        job.error = "The record or provider response could not be validated. Check setup or retry."
        message = session.get(Message, job.message_id)
        for key, value in vars(FakeMailbox(None, None).get("message-1")).items():
            setattr(message, key, value)
        message.state = "pending"
        message.result_json = json.dumps(
            {"probability": 0.99, "kind": "application", "confidence": 0.99}
        )
    assert importer.resume(scan, 1)["state"] == "completed"
    assert FakeAnalyzer.calls == 0
    assert len(tracker.reviews(search)) == 1
    with tracker.db.sessions() as session:
        assert session.scalar(select(Job.state)) == "review"
