import json

import pytest

from job_tracker.credentials import Credentials
from job_tracker.db import Account
from job_tracker.email import register
from job_tracker.errors import UserFacingError
from job_tracker.ui.bridge import Bridge, Work
from job_tracker.worker import Importer


def session_vault():
    vault = Credentials()
    vault.get = lambda name: vault.memory.get(name, "")
    return vault


def test_provider_filter_never_opens_unselected_mailbox(tracker):
    vault = session_vault()
    for provider in ("gmail", "outlook"):
        vault.save(provider, "synthetic-token", False)
        register(tracker, provider, provider + "@example.org", provider)
    opened = []

    class Mailbox:
        def __init__(self, account, _vault):
            opened.append(account["provider"])

        def list_ids(self, *_args):
            return ["synthetic-id"]

    importer = Importer(tracker, vault, mailbox_factory=Mailbox)
    plan = importer.preview("2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z", "outlook")
    assert opened == ["outlook"] and plan["total"] == 1
    importer.preview("2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z", "all")
    assert opened == ["outlook", "gmail", "outlook"]
    with pytest.raises(ValueError):
        importer.preview("2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z", "invalid")


def test_provider_requires_its_own_connected_account(tracker):
    vault = session_vault()
    vault.save("gmail", "synthetic-token", False)
    register(tracker, "gmail", "test@example.org", "gmail")
    with pytest.raises(UserFacingError, match="Outlook"):
        Importer(tracker, vault).preview("2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z", "outlook")


def test_setup_survives_restart_and_preserves_existing_search(qapp, tracker):
    vault = session_vault()
    bridge = Bridge(tracker, vault)
    assert bridge.setupNeeded and not bridge.microsoftClient and not bridge.googleConfigured
    bridge.selectProvider("outlook")
    bridge.saveMicrosoftClient("11111111-2222-3333-4444-555555555555")
    assert bridge.microsoftClient == "11111111-2222-3333-4444-555555555555"
    assert bridge.nameInitialSearch("2026 Co-op")
    bridge.stop()
    restarted = Bridge(tracker, vault)
    assert restarted.setupNeeded and restarted.selectedProvider == "outlook"
    assert restarted.searches[0]["name"] == "2026 Co-op"
    assert len(restarted.searches) == 1
    restarted.finishSetup()
    restarted.stop()
    final = Bridge(tracker, vault)
    assert not final.setupNeeded
    final.stop()


def test_provider_change_invalidates_preview_but_not_records(qapp, tracker):
    bridge = Bridge(tracker, session_vault())
    bridge.saveApplication(json.dumps({"company": "Example", "role": "Developer"}), 0)
    bridge._scan_plan = {"search_id": bridge.selectedSearch}
    bridge.selectProvider("outlook")
    assert not bridge._scan_plan and len(bridge.applications) == 1
    bridge.startHistory(1)
    assert "Preview" in bridge.message
    bridge._busy = True
    bridge.selectProvider("gmail")
    assert bridge.selectedProvider == "outlook"
    bridge._busy = False
    bridge.stop()


def test_automatic_poll_only_advances_selected_provider_checkpoint(qapp, tracker):
    vault = session_vault()
    vault.save("openai", "synthetic-key", False)
    for provider in ("gmail", "outlook"):
        vault.save(provider, "synthetic-token", False)
        register(tracker, provider, provider + "@example.org", provider)
    with tracker.db.sessions.begin() as session:
        session.get(Account, 1).last_sync = "2026-01-01T00:00:00+00:00"
        session.get(Account, 2).last_sync = "2026-02-01T00:00:00+00:00"
    bridge = Bridge(tracker, vault)
    bridge.selectProvider("outlook")
    bridge.configureAI(True, "0.25", "1")
    calls = []
    bridge.importer.preview = lambda start, end, provider: (
        calls.append((start, end, provider)) or {}
    )
    bridge.importer.create_scan = lambda *_args: 0
    bridge.importer.run = lambda *_args: {"state": "completed", "spent": 0}

    def run_inline(action, complete, **_kwargs):
        bridge._work = Work(action)
        complete(action())

    bridge.background = run_inline
    bridge.poll()
    assert calls[0][0] == "2026-01-31T23:55:00+00:00"
    assert calls[0][2] == "outlook"
    accounts = tracker.accounts()
    assert accounts[0]["last_sync"] == "2026-01-01T00:00:00+00:00"
    assert accounts[1]["last_sync"] == calls[0][1]
    bridge.stop()
