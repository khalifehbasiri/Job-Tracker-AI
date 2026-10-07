from types import SimpleNamespace

import httpx
import pytest

from job_tracker.credentials import Credentials
from job_tracker.email import connect_outlook, register
from job_tracker.errors import UserFacingError
from job_tracker.oauth import MICROSOFT_CLIENT_ID, google_desktop_client
from job_tracker.ui.bridge import Bridge


def test_native_google_config_excludes_user_tokens_and_pins_endpoints():
    config = google_desktop_client(
        {
            "installed": {
                "client_id": "fake.apps.googleusercontent.com",
                "client_secret": "fake-native-client-string",
                "auth_uri": "https://evil.example/auth",
                "token_uri": "https://evil.example/token",
                "refresh_token": "PRIVATE-refresh-token",
                "api_key": "PRIVATE-api-key",
            },
            "access_token": "PRIVATE-access-token",
        }
    )
    assert set(config) == {"installed"}
    assert set(config["installed"]) == {"client_id", "client_secret", "auth_uri", "token_uri"}
    assert "PRIVATE" not in str(config)
    assert config["installed"]["token_uri"] == "https://oauth2.googleapis.com/token"
    with pytest.raises(UserFacingError):
        google_desktop_client({"web": {"client_id": "web-client"}})


@pytest.mark.parametrize("mailbox_status", [200, 403, 404])
def test_outlook_only_registers_after_mailbox_access_succeeds(tracker, monkeypatch, mailbox_status):
    app = SimpleNamespace(acquire_token_interactive=lambda **kwargs: {"access_token": "fake"})
    cache = SimpleNamespace(serialize=lambda: "fake-cache")
    monkeypatch.setattr("job_tracker.email.microsoft_app", lambda _id: (app, cache))
    client_type = httpx.Client

    def handle(request):
        if request.url.path.endswith("/me"):
            return httpx.Response(200, json={"mail": "test@outlook.example"})
        return httpx.Response(mailbox_status, json={"value": [], "error": "PRIVATE-details"})

    monkeypatch.setattr(
        "job_tracker.email.httpx.Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    vault = Credentials()
    if mailbox_status == 200:
        assert connect_outlook(tracker, vault, MICROSOFT_CLIENT_ID, False) == "test@outlook.example"
        assert tracker.accounts()[0]["provider"] == "outlook"
        assert vault.get(tracker.accounts()[0]["credential_ref"])
    else:
        with pytest.raises(UserFacingError, match="mailbox access failed") as caught:
            connect_outlook(tracker, vault, MICROSOFT_CLIENT_ID, False)
        assert "PRIVATE" not in str(caught.value)
        assert not tracker.accounts() and not vault.memory


def test_connection_success_refreshes_settings_and_failure_stays_visible(qapp, qtbot, tracker):
    vault = Credentials()
    vault.get = lambda _name: "fake-token"
    bridge = Bridge(tracker, vault)
    bridge.timer.stop()

    def success():
        register(tracker, "outlook", "test@outlook.example", "fake-ref")
        return "test@outlook.example"

    bridge.connectMailbox("outlook", success)
    assert bridge.connectingProvider == "outlook"
    assert not bridge.scanActive
    qtbot.waitUntil(lambda: not bridge.busy, timeout=3000)
    assert bridge.accounts[0]["provider"] == "outlook"
    assert bridge.accounts[0]["connected"]
    assert "connected read-only" in bridge.mailboxStatuses["outlook"]

    def failure():
        raise UserFacingError("Sign-in was cancelled.")

    bridge.connectMailbox("gmail", failure)
    qtbot.waitUntil(lambda: not bridge.busy, timeout=3000)
    bridge.feedback("Some other operation finished.")
    assert "connection was not saved" in bridge.mailboxStatuses["gmail"]
    assert "cancelled" in bridge.mailboxStatuses["gmail"]
    bridge.stop()
