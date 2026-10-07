from types import SimpleNamespace

import pytest

from job_tracker.ai import Analyzer
from job_tracker.credentials import Credentials
from job_tracker.email import Email


class MemoryBackend:
    def __init__(self):
        self.values = {}

    def set_password(self, service, name, value):
        self.values[name] = value

    def get_password(self, service, name):
        return self.values.get(name)

    def delete_password(self, service, name):
        del self.values[name]


def test_session_only_does_not_write_key_store(monkeypatch):
    vault = Credentials()
    backend = MemoryBackend()
    monkeypatch.setattr(vault, "backend", lambda: backend)
    vault.save("openai", "fake-session-key", persist=False)
    assert vault.get("openai") == "fake-session-key"
    assert not backend.values
    vault.save("openai", "fake-persistent-key")
    assert backend.values["openai"] == "fake-persistent-key"
    vault.remove("openai")
    assert vault.get("openai") == ""


def test_no_plaintext_fallback(monkeypatch):
    vault = Credentials()
    monkeypatch.setattr(
        vault, "backend", lambda: (_ for _ in ()).throw(RuntimeError("unavailable"))
    )
    with pytest.raises(ValueError, match="securely"):
        vault.save("openai", "never-write-this")
    assert not vault.memory


def test_extraction_has_no_tools_and_rejects_unsupported_evidence():
    calls, charges = [], []

    class Responses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                status="completed",
                usage=SimpleNamespace(model_dump=lambda: {"input_tokens": 50, "output_tokens": 50}),
                output_text='{"company":"Company","role":"Developer","requisition_id":null,'
                '"applied_on":null,"deadline_at":null,"interview_at":null,'
                '"evidence":"invented evidence"}',
            )

    analyzer = Analyzer.__new__(Analyzer)
    analyzer.client = SimpleNamespace(responses=Responses())
    message = Email("1", "t", "jobs@example.org", "Hello", "Original email", "2026-10-01T00:00:00Z")

    def bill(operation, model, amount):
        charges.append(operation)
        return 1

    with pytest.raises(ValueError, match="evidence"):
        analyzer.extract(message, bill)
    assert charges == [
        "extract",
        "settle",
    ]  # Record actual usage even when validation rejects output.
    assert calls[0]["store"] is False
    assert "tools" not in calls[0]
    assert calls[0]["max_output_tokens"] == 1024
    assert calls[0]["text"]["format"]["strict"] is True
