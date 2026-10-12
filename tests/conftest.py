import pytest

from job_tracker.credentials import Credentials
from job_tracker.db import Database
from job_tracker.services import Tracker


class MemoryCredentialStore:
    """Every test gets its own store; fake session keys must never delete real keys."""

    def __init__(self):
        self.values = {}

    def get_password(self, service, name):
        return self.values.get((service, name))

    def set_password(self, service, name, value):
        self.values[service, name] = value

    def delete_password(self, service, name):
        self.values.pop((service, name), None)


@pytest.fixture(autouse=True)
def isolated_credential_store(monkeypatch):
    store = MemoryCredentialStore()
    monkeypatch.setattr(Credentials, "backend", lambda _self: store)

    def prohibit_os_store():
        raise AssertionError("Tests must never access the user's OS credential store.")

    monkeypatch.setattr("job_tracker.credentials.keyring.get_keyring", prohibit_os_store)
    return store


@pytest.fixture
def tracker(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    yield Tracker(db)
    db.close()
