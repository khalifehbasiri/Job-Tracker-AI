import json
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QThread, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle

from job_tracker.credentials import Credentials
from job_tracker.db import Scan
from job_tracker.desktop_lock import acquire_database_lock
from job_tracker.ui.bridge import Bridge


def test_qml_pages_and_live_records(qapp, qtbot, tracker):
    QQuickStyle.setStyle("Basic")
    search = tracker.create_search("Test search")
    with tracker.db.sessions.begin() as session:
        session.add(
            Scan(
                search_id=search,
                start_at="2026-09-01T00:00:00Z",
                end_at="2026-10-01T00:00:00Z",
                budget=1,
                state="paused",
                error="Mailbox request timed out. Resume to retry.",
            )
        )
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
    bridge._busy, bridge._operation = True, "scan"
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
