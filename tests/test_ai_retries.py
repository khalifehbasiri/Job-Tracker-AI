import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from sqlalchemy import select
from test_scan_recovery import setup_importer
from test_worker import FakeAnalyzer, FakeMailbox

from job_tracker.ai import Analyzer
from job_tracker.db import Job, Message, Usage
from job_tracker.retries import retry_after_seconds, retry_delay, transient_ai_error


def api_error(status=503, body=None, headers=None):
    response = httpx.Response(
        status,
        headers=headers,
        request=httpx.Request("POST", "https://api.openai.com/v1/decisions"),
    )
    return APIStatusError("PRIVATE email/token/provider text", response=response, body=body or {})


@pytest.mark.parametrize("status", [408, 409, 500, 502, 503, 504])
def test_transient_api_status_can_retry(status):
    assert transient_ai_error(api_error(status))


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422, 429])
def test_permanent_or_ambiguous_status_does_not_retry(status):
    assert not transient_ai_error(api_error(status))


@pytest.mark.parametrize("error_type", [APIConnectionError, APITimeoutError])
def test_connection_and_timeout_can_retry(error_type):
    assert transient_ai_error(error_type(request=httpx.Request("POST", "https://example.org")))


@pytest.mark.parametrize("nested", [False, True])
def test_rate_limit_retries_but_quota_failure_does_not(nested):
    rate = {"code": "rate_limit_exceeded", "type": "rate_limit_error"}
    quota = {"code": "insufficient_quota", "type": "rate_limit_error"}
    assert transient_ai_error(api_error(429, {"error": rate} if nested else rate))
    assert not transient_ai_error(api_error(429, {"error": quota} if nested else quota))


def test_server_can_disable_retry():
    assert not transient_ai_error(api_error(headers={"x-should-retry": "false"}))


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"retry-after": "30"}, 30),
        ({"retry-after-ms": "15000", "retry-after": "30"}, 15),
        ({"retry-after-ms": "invalid", "retry-after": "30"}, 30),
        ({"retry-after": "NaN"}, None),
        ({"retry-after": "inf"}, None),
        ({"retry-after": "-5"}, None),
        ({"retry-after": "PRIVATE-invalid-header"}, None),
    ],
)
def test_retry_after_formats(headers, expected):
    assert retry_after_seconds(api_error(headers=headers)) == expected


def test_retry_after_date_and_overlong_delays():
    future = format_datetime(datetime.now(UTC) + timedelta(seconds=90), usegmt=True)
    assert 88 < retry_after_seconds(api_error(headers={"retry-after": future})) <= 90
    assert retry_delay(api_error(headers={"retry-after": "121"}), 1) is None
    assert retry_delay(api_error(headers={"retry-after": "1e999"}), 1) is None


def test_backoff_grows_with_jitter_and_honors_server_minimum(monkeypatch):
    monkeypatch.setattr("job_tracker.retries.uniform", lambda _a, _b: 0.5)
    assert [retry_delay(api_error(), attempt) for attempt in (1, 2, 3)] == [2.5, 4.5, 8.5]
    assert retry_delay(api_error(headers={"retry-after": "30"}), 1) == 30


def plan_scan(importer, search, budget=1):
    plan = importer.preview("2026-09-01T00:00:00Z", "2026-11-01T00:00:00Z")
    return importer.create_scan(search, plan, budget), plan


def skip_wait(monkeypatch, importer):
    delays = []
    monkeypatch.setattr(importer.cancelled, "wait", lambda delay: delays.append(delay) or False)
    return delays


def test_503_recovers_without_manual_resume_and_preserves_reservations(tracker, monkeypatch):
    class Analyzer(FakeAnalyzer):
        dispatches = 0

        def classify(self, message, bill):
            if self.dispatches < 2:
                bill("classify", "gpt-6-luna", 0.01)
                type(self).dispatches += 1
                raise api_error()
            type(self).dispatches += 1
            return super().classify(message, bill)

    importer, search = setup_importer(tracker, analyzer=Analyzer)
    delays = skip_wait(monkeypatch, importer)
    scan, plan = plan_scan(importer, search)
    progress = []
    result = importer.run(scan, plan, progress.append)
    assert result["state"] == "completed" and not result["error"]
    assert Analyzer.dispatches == 3 and len(delays) == 2
    assert len(tracker.applications(search)) == 1
    with tracker.db.sessions() as session:
        usage = list(session.scalars(select(Usage)))
        assert [row.operation for row in usage] == ["classify"] * 3 + ["extract"]
        assert sum(row.input_tokens == 0 for row in usage) == 2
        assert result["spent"] == pytest.approx(sum(row.cost for row in usage))
        assert session.scalar(select(Job)).attempts == 1
    assert any("Retrying OpenAI classification" in text for text in progress)
    assert not any("PRIVATE" in text for text in progress)
    # Re-scanning the same range reuses completed work without another dispatch.
    second, plan = plan_scan(importer, search)
    assert importer.run(second, plan)["state"] == "completed"
    assert Analyzer.dispatches == 3


def test_extraction_retry_keeps_successful_classification(tracker, monkeypatch):
    class Analyzer(FakeAnalyzer):
        classifications = extractions = 0

        def classify(self, message, bill):
            type(self).classifications += 1
            return super().classify(message, bill)

        def extract(self, message, bill):
            type(self).extractions += 1
            if self.extractions < 3:
                bill("extract", "gpt-5.4-mini", 0.02)
                raise api_error()
            return super().extract(message, bill)

    importer, search = setup_importer(tracker, analyzer=Analyzer)
    skip_wait(monkeypatch, importer)
    scan, plan = plan_scan(importer, search)
    assert importer.run(scan, plan)["state"] == "completed"
    assert (Analyzer.classifications, Analyzer.extractions) == (1, 3)
    with tracker.db.sessions() as session:
        assert "extraction" in json.loads(session.scalar(select(Message.result_json)))
    assert len(tracker.events(tracker.applications(search)[0]["id"])) == 1


def test_exhausted_retries_stop_before_other_emails_and_resume_safely(tracker, monkeypatch):
    class Mailbox(FakeMailbox):
        def list_ids(self, *args):
            return ["one", "two", "three"]

    class Analyzer(FakeAnalyzer):
        dispatches = 0
        unavailable = True

        def classify(self, message, bill):
            if self.unavailable:
                bill("classify", "gpt-6-luna", 0.01)
                type(self).dispatches += 1
                raise api_error()
            return super().classify(message, bill)

    importer, search = setup_importer(tracker, Mailbox, Analyzer)
    delays = skip_wait(monkeypatch, importer)
    scan, plan = plan_scan(importer, search)
    result = importer.run(scan, plan)
    assert result["state"] == "paused" and "after 4 attempts" in result["error"]
    assert "PRIVATE" not in result["error"] and result["spent"] == pytest.approx(0.04)
    assert Analyzer.dispatches == 4 and len(delays) == 3
    counts = importer.scans(search)[0]
    assert (counts["failed"], counts["pending"]) == (1, 2)
    Analyzer.unavailable = False
    assert importer.resume(scan, 1)["state"] == "completed"
    with tracker.db.sessions() as session:
        assert all(not job.error and not job.retry_at for job in session.scalars(select(Job)))
    assert len(tracker.applications(search)) == 1


def test_retry_budget_blocks_dispatch_before_exceeding_limit(tracker, monkeypatch):
    class Analyzer(FakeAnalyzer):
        dispatches = 0

        def classify(self, message, bill):
            bill("classify", "gpt-6-luna", 0.01)
            type(self).dispatches += 1
            raise api_error()

    importer, search = setup_importer(tracker, analyzer=Analyzer)
    skip_wait(monkeypatch, importer)
    scan, plan = plan_scan(importer, search, budget=0.015)
    result = importer.run(scan, plan)
    assert result["state"] == "paused" and "Spending limit" in result["error"]
    assert Analyzer.dispatches == 1 and result["spent"] == pytest.approx(0.01)
    with tracker.db.sessions() as session:
        assert len(list(session.scalars(select(Usage)))) == 1


def test_quota_error_and_overlong_server_delay_stop_without_more_requests(tracker, monkeypatch):
    class Analyzer(FakeAnalyzer):
        dispatches = 0

        def classify(self, message, bill):
            bill("classify", "gpt-6-luna", 0.01)
            type(self).dispatches += 1
            raise api_error(429, {"error": {"code": "insufficient_quota"}})

    importer, search = setup_importer(tracker, analyzer=Analyzer)
    delays = skip_wait(monkeypatch, importer)
    scan, plan = plan_scan(importer, search)
    result = importer.run(scan, plan)
    assert result["state"] == "paused" and "credits or quota" in result["error"]
    assert Analyzer.dispatches == 1 and not delays

    def unavailable(_message, bill):
        bill("classify", "gpt-6-luna", 0.01)
        raise api_error(headers={"retry-after": "121"})

    monkeypatch.setattr(
        Analyzer, "classify", lambda _self, message, bill: unavailable(message, bill)
    )
    result = importer.resume(scan, 1)
    assert result["state"] == "paused" and "two-minute" in result["error"]
    assert result["spent"] == pytest.approx(0.02) and not delays


def test_pause_interrupts_backoff_and_preserves_failed_request_reservation(tracker, monkeypatch):
    class Analyzer(FakeAnalyzer):
        dispatches = 0
        unavailable = True

        def classify(self, message, bill):
            if self.unavailable:
                bill("classify", "gpt-6-luna", 0.01)
                type(self).dispatches += 1
                raise api_error()
            return super().classify(message, bill)

    importer, search = setup_importer(tracker, analyzer=Analyzer)

    def pause(_delay):
        importer.cancelled.set()
        return True

    monkeypatch.setattr(importer.cancelled, "wait", pause)
    scan, plan = plan_scan(importer, search)
    result = importer.run(scan, plan)
    assert result["state"] == "paused" and result["spent"] == pytest.approx(0.01)
    assert Analyzer.dispatches == 1
    with tracker.db.sessions() as session:
        job = session.scalar(select(Job))
        assert job.state == "pending" and job.attempts == 0
    importer.cancelled.clear()
    Analyzer.unavailable = False
    assert importer.resume(scan, 1)["state"] == "completed"


def test_real_sdk_recovery_bills_each_dispatch_and_caches_classification(tracker, monkeypatch):
    dispatches = {"decisions": 0, "responses": 0}
    usage = {
        "input_tokens": 100,
        "output_tokens": 10,
        "total_tokens": 110,
        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 0},
    }

    def handle(request):
        operation = request.url.path.rsplit("/", 1)[-1]
        dispatches[operation] += 1
        failures = 2 if operation == "decisions" else 1
        if dispatches[operation] <= failures:
            return httpx.Response(
                503,
                json={"error": {"message": "PRIVATE provider text", "type": "server_error"}},
            )
        if operation == "decisions":
            return httpx.Response(
                200,
                json={
                    "model": "gpt-6-luna",
                    "usage": usage,
                    "answers": [
                        {"name": "job_related", "type": "predicate", "probability": 0.99},
                        {
                            "name": "event",
                            "type": "choice",
                            "choice": "application",
                            "confidence": 0.99,
                            "probabilities": [],
                        },
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "resp_fictional",
                "object": "response",
                "created_at": 0,
                "model": "gpt-5.4-mini",
                "status": "completed",
                "usage": usage,
                "output": [
                    {
                        "id": "msg_fictional",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "annotations": [],
                                "text": json.dumps(
                                    {
                                        "company": "Example Company",
                                        "role": "Developer",
                                        "requisition_id": "REQ-1",
                                        "applied_on": None,
                                        "deadline_at": None,
                                        "interview_at": None,
                                        "evidence": "We received your application.",
                                    }
                                ),
                            }
                        ],
                    }
                ],
            },
        )

    def factory(_key):
        analyzer = Analyzer.__new__(Analyzer)
        analyzer.client = OpenAI(
            api_key="synthetic-test-key",
            max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(handle)),
        )
        return analyzer

    importer, search = setup_importer(tracker, analyzer=factory)
    skip_wait(monkeypatch, importer)
    scan, plan = plan_scan(importer, search)
    result = importer.run(scan, plan)
    assert result["state"] == "completed"
    assert dispatches == {"decisions": 3, "responses": 2}
    with tracker.db.sessions() as session:
        ledger = list(session.scalars(select(Usage)))
        assert len(ledger) == sum(dispatches.values())
        assert sum(row.input_tokens == 0 for row in ledger) == 3
        assert result["spent"] == pytest.approx(sum(row.cost for row in ledger))
    assert len(tracker.applications(search)) == 1
