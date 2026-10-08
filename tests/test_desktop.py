import json
from pathlib import Path

import pytest
from PySide6.QtCore import QMetaObject, QObject, QThread, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle

from job_tracker.credentials import Credentials
from job_tracker.db import Account, Job, Message, Review, Scan
from job_tracker.desktop_lock import acquire_database_lock
from job_tracker.ui.bridge import Bridge


def visual_item(parent, name):
    if parent.objectName() == name:
        return parent
    for child in parent.childItems():
        found = visual_item(child, name)
        if found is not None:
            return found
    return None


def test_qml_pages_and_live_records(qapp, qtbot, tracker):
    QQuickStyle.setStyle("Basic")
    search = tracker.create_search("Test search")
    with tracker.db.sessions.begin() as session:
        scan = Scan(
            search_id=search,
            start_at="2026-09-01T00:00:00Z",
            end_at="2026-10-01T00:00:00Z",
            budget=1,
            state="paused",
            error="Mailbox request timed out. Resume to retry.",
        )
        session.add(scan)
        account = Account(provider="gmail", address="fictional@example.org", credential_ref="")
        session.add(account)
        session.flush()
        message = Message(
            account_id=account.id,
            provider_id="demo-review",
            subject="A role update",
            sender="careers@example.org",
            body="Searchable hidden kiwi text",
            received_at="2026-10-01T00:00:00Z",
        )
        session.add(message)
        session.flush()
        job = Job(message_id=message.id, search_id=search, scan_id=scan.id, state="review")
        session.add(job)
        session.flush()
        review = Review(
            job_id=job.id,
            search_id=search,
            reason="Uncertain match",
            proposed_json=json.dumps(
                {"kind": "interview", "extraction": {"company": "Company", "role": "Developer"}}
            ),
        )
        session.add(review)
        session.flush()
        review_id = review.id
    vault = Credentials()
    # Test machines must never query a user's existing credential store.
    vault.get = lambda name: ""
    bridge = Bridge(tracker, vault)
    bridge.timer.stop()
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda items: warnings.extend(item.toString() for item in items))
    engine.rootContext().setContextProperty("backend", bridge)
    qml = Path(__file__).parents[1] / "src/job_tracker/ui/Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml)))
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    assert isinstance(window, QQuickWindow)
    bridge.saveApplication(json.dumps({"company": "Company", "role": "Developer"}), 0)
    assert len(bridge.applications) == 1
    for page in range(5):
        window.setProperty("page", page)
        qtbot.wait(80)
        assert not window.grabWindow().isNull()
    assert bridge.selectedSearch == search
    window.setProperty("page", 2)
    qtbot.wait(30)
    assert len(bridge.reviews) == 1
    card = visual_item(window.contentItem(), f"reviewCard-{review_id}")
    body = visual_item(window.contentItem(), f"reviewBody-{review_id}")
    assert not card.property("expanded") and not body.property("visible")
    header = visual_item(window.contentItem(), f"reviewHeader-{review_id}")
    assert QMetaObject.invokeMethod(header, "clicked")
    qtbot.wait(30)
    assert card.property("expanded") and body.property("visible")
    bridge.refresh()
    qtbot.wait(30)
    # Refreshes while scanning must not collapse an email the user is reading.
    assert visual_item(window.contentItem(), f"reviewCard-{review_id}").property("expanded")
    review_filter = window.findChild(QObject, "reviewFilter")
    review_filter.setProperty("text", "kiwi")
    qtbot.wait(30)
    assert len(window.property("filteredReviews").toVariant()) == 1
    review_filter.setProperty("text", "no matching email")
    qtbot.wait(30)
    assert len(window.property("filteredReviews").toVariant()) == 0
    review_filter.setProperty("text", "")
    for dark in (True, False):
        bridge.setDarkMode(dark)
        qtbot.wait(30)
        assert bridge.darkMode == dark
        assert window.property("color").name() == ("#12201d" if dark else "#f4f6f1")
        for popup in ("authHelp", "editSearchDialog"):
            dialog = window.findChild(QObject, popup)
            dialog.setProperty("visible", True)
            qtbot.wait(30)
            assert dialog.property("height") < window.height()
            dialog.setProperty("visible", False)
    bridge._busy, bridge._operation = True, "scan"
    bridge.changed.emit()
    bridge.feedback("Processing email 321 of 690…")
    qtbot.wait(80)
    banner = window.findChild(QObject, "statusBanner")
    button = window.findChild(QObject, "pauseScanButton")
    label = window.findChild(QObject, "statusText")
    assert button.property("visible")
    assert banner.property("height") >= button.property("height") + 24
    assert button.property("y") == pytest.approx(
        (banner.property("height") - 24 - button.property("height")) / 2
    )
    assert label.property("y") >= 0
    bridge._operation = "oauth"
    bridge.changed.emit()
    qtbot.wait(30)
    assert not button.property("visible")
    bridge._busy = False
    assert bridge.editSearch("Updated search", "2026-01-01", "2026-12-31", False)
    assert bridge.searches[0]["name"] == "Updated search"
    assert not bridge.editSearch("Bad search", "2027-01-01", "2026-01-01", False)
    window.setProperty("page", 3)
    with tracker.db.sessions.begin() as session:
        session.get(Scan, bridge.scans[0]["id"]).state = "completed"
    bridge.refresh()
    qtbot.wait(30)
    resume = visual_item(window.contentItem(), f"resumeImport-{bridge.scans[0]['id']}")
    assert not resume.property("visible")
    bridge.removeImport(bridge.scans[0]["id"])
    assert not bridge.scans and len(bridge.applications) == 1 and len(bridge.reviews) == 1
    wizard = window.findChild(QObject, "setupWizard")
    wizard.setProperty("visible", True)
    for step in range(4):
        wizard.setProperty("step", step)
        qtbot.wait(40)
        assert wizard.property("height") < window.height()
        assert not window.grabWindow().isNull()
    wizard.setProperty("visible", False)
    bridge.selectProvider("outlook")
    qtbot.wait(40)
    assert window.findChild(QObject, "settingsProviderSelector").property("currentIndex") == 1
    assert window.findChild(QObject, "historyProviderSelector").property("currentIndex") == 1
    assert not warnings, "\n".join(warnings)
    window.close()
    engine.deleteLater()
    qapp.processEvents()
    bridge.stop()


def test_background_completion_runs_on_ui_thread(qapp, qtbot, tracker):
    vault = Credentials()
    vault.get = lambda name: ""
    bridge = Bridge(tracker, vault)
    bridge.timer.stop()
    completed = []
    bridge.background(
        lambda: "done", lambda result: completed.append((result, QThread.currentThread()))
    )
    qtbot.waitUntil(lambda: bool(completed), timeout=3000)
    assert completed[0] == ("done", qapp.thread())
    assert not bridge.busy
    bridge.stop()


def test_single_instance_per_database(qapp, tmp_path):
    path = tmp_path / "records.sqlite3"
    first = acquire_database_lock(path)
    try:
        with pytest.raises(ValueError, match="already open"):
            acquire_database_lock(path)
    finally:
        first.unlock()
    replacement = acquire_database_lock(path)
    replacement.unlock()


def test_failed_key_save_does_not_report_success(qapp, tracker, monkeypatch):
    vault = Credentials()
    vault.get = lambda name: "old-key"
    monkeypatch.setattr(
        vault, "save", lambda *args: (_ for _ in ()).throw(ValueError("Cannot save securely"))
    )
    bridge = Bridge(tracker, vault)
    bridge.saveKey("replacement-key", True)
    assert "Could not save the key securely" in bridge.message
    bridge.stop()


def test_records_refresh_during_background_scan(qapp, qtbot, tracker):
    vault = Credentials()
    vault.get = lambda name: ""
    bridge = Bridge(tracker, vault)
    bridge.timer.stop()
    bridge._busy = True
    tracker.save_application(bridge.selectedSearch, {"company": "New record", "role": "Engineer"})
    assert not bridge.applications
    bridge.refresh_timer.setInterval(10)
    qtbot.waitUntil(lambda: bool(bridge.applications), timeout=2000)
    assert bridge.applications[0]["company"] == "New record"
    bridge._busy = False
    bridge.stop()
