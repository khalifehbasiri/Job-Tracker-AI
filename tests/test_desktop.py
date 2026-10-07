import json
from pathlib import Path

from PySide6.QtCore import QThread, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle

from job_tracker.credentials import Credentials
from job_tracker.ui.bridge import Bridge


def test_qml_pages_and_live_records(qapp, qtbot, tracker):
    QQuickStyle.setStyle("Basic")
    search = tracker.create_search("Test search")
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
