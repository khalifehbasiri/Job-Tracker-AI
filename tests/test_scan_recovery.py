import httpx
from openai import AuthenticationError
from sqlalchemy import select
from test_worker import FakeAnalyzer, FakeMailbox

from job_tracker.credentials import Credentials
from job_tracker.db import Job, Message, Scan
from job_tracker.email import register
from job_tracker.worker import Importer


def setup_importer(tracker, mailbox=FakeMailbox, analyzer=FakeAnalyzer):
    FakeAnalyzer.calls, FakeAnalyzer.fail = 0, False
    vault = Credentials()
    vault.memory["mailbox"] = "fake-token"
    register(tracker, "gmail", "candidate@example.org", "mailbox")
    search = tracker.create_search("Search")
    importer = Importer(tracker, vault, analyzer, mailbox)
    return importer, search


def test_old_saved_messages_process_before_download_failure_and_resume(tracker):
    class Mailbox(FakeMailbox):
        fail = True

        def list_ids(self, *args):
            return ["new-message", "saved-message"]

        def get(self, provider_id):
            if self.fail and provider_id == "new-message":
                raise httpx.ReadTimeout("PRIVATE email and bearer token")
            return super().get(provider_id)

    importer, search = setup_importer(tracker, Mailbox)
    plan = importer.preview("2026-09-01T00:00:00Z", "2026-11-01T00:00:00Z")
    scan = importer.create_scan(search, plan, 1)
    # Simulate the original version: email downloaded, job waiting for all other downloads.
    cached_job = importer.stage_message(tracker.accounts()[0], "saved-message", scan, search)
    with tracker.db.sessions.begin() as session:
        row = session.get(Message, session.get(Job, cached_job).message_id)
        for key, value in vars(FakeMailbox(None, None).get("saved-message")).items():
            setattr(row, key, value)
        row.state = "pending"
    result = importer.run(scan, plan)
    assert result["state"] == "paused"
    assert "timed out" in result["error"]
    assert "PRIVATE" not in result["error"]
    assert len(tracker.applications(search)) == 1
    counts = importer.scans(search)[0]
    assert (counts["processed"], counts["failed"]) == (1, 1)
    Mailbox.fail = False
    assert importer.resume(scan, 1)["state"] == "completed"
    assert importer.scans(search)[0]["processed"] == 2
    assert FakeAnalyzer.calls == 2  # Completed saved email never billed again.


def test_disappearing_email_does_not_block_other_records(tracker):
    class Mailbox(FakeMailbox):
        def list_ids(self, *args):
            return ["deleted", "remaining"]

        def get(self, provider_id):
            if provider_id == "deleted":
                response = httpx.Response(404, request=httpx.Request("GET", "https://example.org"))
                raise httpx.HTTPStatusError("PRIVATE", request=response.request, response=response)
            return super().get(provider_id)

    importer, search = setup_importer(tracker, Mailbox)
    plan = importer.preview("2026-09-01T00:00:00Z", "2026-11-01T00:00:00Z")
    scan = importer.create_scan(search, plan, 1)
    assert importer.run(scan, plan)["state"] == "completed"
    assert importer.scans(search)[0]["unavailable"] == 1
    assert len(tracker.applications(search)) == 1
    assert FakeAnalyzer.calls == 1


def test_api_auth_failure_stops_scan_instead_of_repeating_requests(tracker):
    class Mailbox(FakeMailbox):
        def list_ids(self, *args):
            return ["one", "two", "three"]

    class Analyzer(FakeAnalyzer):
        calls = 0

        def classify(self, message, bill):
            type(self).calls += 1
            bill("classify", "gpt-6-luna", 0.01)
            response = httpx.Response(401, request=httpx.Request("POST", "https://api.openai.com"))
            raise AuthenticationError("PRIVATE-key-and-email", response=response, body={})

    importer, search = setup_importer(tracker, Mailbox, Analyzer)
    plan = importer.preview("2026-09-01T00:00:00Z", "2026-11-01T00:00:00Z")
    result = importer.run(importer.create_scan(search, plan, 1), plan)
    assert result["state"] == "paused"
    assert "API key" in result["error"]
    assert "PRIVATE" not in result["error"]
    assert Analyzer.calls == 1
    counts = importer.scans(search)[0]
    assert (counts["failed"], counts["pending"]) == (1, 2)
    with tracker.db.sessions() as session:
        assert "PRIVATE" not in session.scalar(select(Scan.error))
        assert "PRIVATE" not in session.scalar(select(Job.error).where(Job.state == "error"))
