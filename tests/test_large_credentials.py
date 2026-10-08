import pytest

from job_tracker.credentials import Credentials
from job_tracker.errors import UserFacingError, describe_error


class SizeLimitedBackend:
    """Simulate Windows Credential Manager's UTF-16 payload ceiling."""

    def __init__(self):
        self.values = {}
        self.fail_after = None
        self.writes = 0

    def get_password(self, service, name):
        return self.values.get(name)

    def set_password(self, service, name, value):
        if len(value.encode("utf-16-le")) > 2560:
            raise ValueError("PRIVATE credential is too large")
        self.writes += 1
        if self.fail_after == self.writes:
            raise ValueError("PRIVATE simulated secure storage failure")
        self.values[name] = value

    def delete_password(self, service, name):
        del self.values[name]


def vault_using(backend):
    vault = Credentials()
    vault.backend = lambda: backend
    return vault


@pytest.mark.parametrize("value", ["synthetic-token" * 1000, "🔐漢字" * 1000])
def test_large_credentials_survive_restart_and_remove_every_piece(value):
    backend = SizeLimitedBackend()
    vault_using(backend).save("outlook-test", value)
    assert len(backend.values) > 1
    assert all(len(part.encode("utf-16-le")) <= 2560 for part in backend.values.values())
    restarted = vault_using(backend)
    assert restarted.get("outlook-test") == value
    restarted.remove("outlook-test")
    assert not backend.values
    assert restarted.get("outlook-test") == ""


def test_replace_large_cache_deletes_old_generation_and_supports_small_values():
    backend = SizeLimitedBackend()
    vault = vault_using(backend)
    vault.save("outlook-test", "old-cache" * 1000)
    old_pieces = set(backend.values) - {"outlook-test"}
    vault.save("outlook-test", "new-cache" * 1000)
    assert not old_pieces.intersection(backend.values)
    assert vault_using(backend).get("outlook-test") == "new-cache" * 1000
    vault.save("outlook-test", "small-legacy-compatible-value")
    assert backend.values == {"outlook-test": "small-legacy-compatible-value"}


@pytest.mark.parametrize("failed_write", [2, 17])
def test_partial_write_or_pointer_failure_keeps_previous_credential(failed_write):
    backend = SizeLimitedBackend()
    vault = vault_using(backend)
    vault.save("outlook-test", "previous-cache")
    # 12,000 UTF-8 bytes make 16 pieces, followed by the pointer commit.
    backend.fail_after = backend.writes + failed_write
    with pytest.raises(UserFacingError) as caught:
        vault.save("outlook-test", "x" * 12000)
    assert "PRIVATE" not in describe_error(caught.value)
    assert backend.values == {"outlook-test": "previous-cache"}
    assert vault_using(backend).get("outlook-test") == "previous-cache"
    assert vault.get("outlook-test") == "previous-cache"


def test_session_only_replacement_removes_all_saved_cache_pieces():
    backend = SizeLimitedBackend()
    vault = vault_using(backend)
    vault.save("outlook-test", "persistent-cache" * 1000)
    vault.save("outlook-test", "session-cache" * 1000, persist=False)
    assert not backend.values
    assert vault.get("outlook-test") == "session-cache" * 1000
    assert vault_using(backend).get("outlook-test") == ""


def test_missing_or_corrupt_piece_is_never_returned_as_a_token():
    backend = SizeLimitedBackend()
    vault_using(backend).save("outlook-test", "synthetic-cache" * 1000)
    part = next(name for name in backend.values if "/chunk/" in name)
    backend.values[part] = "malformed-payload"
    assert vault_using(backend).get("outlook-test") == ""
    del backend.values[part]
    assert vault_using(backend).get("outlook-test") == ""
    vault_using(backend).remove("outlook-test")
    assert not backend.values
