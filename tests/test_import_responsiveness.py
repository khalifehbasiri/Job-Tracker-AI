"""Regressions for GUI stalls while an email import is running."""

import json
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QPointF, Qt, QThread, QTimer, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from sqlalchemy import select
from test_ai_retries import api_error
from test_worker import FakeAnalyzer, FakeMailbox

from job_tracker.credentials import Credentials
from job_tracker.db import Account, Application, Job, Message, Review, Scan
from job_tracker.email import register
from job_tracker.ui.bridge import Bridge, Work


def test_progress_does_not_refresh_models(qapp, tracker):
    vault = Credentials()
    vault.get = lambda _name: ""
    bridge = Bridge(tracker, vault, onboarding=False)
    notifications = []
    bridge.changed.connect(lambda: notifications.append(bridge.message))
    try:
        for index in range(2610):
            bridge.feedback(f"Queuing email {index + 1} of 2610…")
        assert not notifications, "Progress must not invalidate every model and setting binding."
        assert "2610" in bridge.message
    finally:
        bridge.stop()


def test_progress_queue_is_bounded(monkeypatch):
    monkeypatch.setattr("job_tracker.ui.bridge.monotonic", lambda: 1.0)
    work = Work(lambda: None)
    updates = []
    work.signals.progress.connect(updates.append)
    for index in range(2610):
        work.report_progress(f"Queuing email {index + 1}")
    assert len(updates) == 1


def test_large_import_remains_interactive_with_blocked_refresh(qapp, qtbot, tracker, monkeypatch):
    """Real staging worker + QML mouse input, with no provider or paid AI calls."""
    search = tracker.create_search("Large import")
    with tracker.db.sessions.begin() as session:
        account = Account(provider="gmail", address="fictional@example.org", credential_ref="fake")
        session.add(account)
        session.flush()
        account_id = account.id
        session.add_all(
            [
                Application(search_id=search, company=f"Company {index}", role="Developer")
                for index in range(408)
            ]
        )
        old_scan = Scan(
            search_id=search,
            start_at="2026-09-01",
            end_at="2026-10-01",
            budget=1,
            state="completed",
        )
        session.add(old_scan)
        session.flush()
        for index in range(103):
            message = Message(
                account_id=account_id,
                provider_id=f"old-{index}",
                subject=f"Review {index}",
                sender="careers@example.org",
                body="Searchable kiwi " + "Fictional email text. " * 200,
                received_at="2026-09-01T00:00:00Z",
            )
            session.add(message)
            session.flush()
            job = Job(message_id=message.id, search_id=search, scan_id=old_scan.id, state="review")
            session.add(job)
            session.flush()
            session.add(
                Review(
                    job_id=job.id,
                    search_id=search,
                    reason="Uncertain match",
                    proposed_json=json.dumps(
                        {
                            "kind": "interview",
                            "extraction": {"company": "Example", "role": "Developer"},
                        }
                    ),
                )
            )
    vault = Credentials()
    vault.get = lambda _name: "fake"
    bridge = Bridge(tracker, vault, onboarding=False)
    bridge.timer.stop()
    staged, release_stage, reading, release_read = Event(), Event(), Event(), Event()
    stage_threads, read_threads, progress_threads = [], [], []
    original_stage, original_apps = bridge.importer.stage_message, tracker.applications

    def stage(*args, **kwargs):
        result = original_stage(*args, **kwargs)
        stage_threads.append(QThread.currentThread())
        staged.set()
        assert release_stage.wait(10)
        return result

    def apps(search_id):
        read_threads.append(QThread.currentThread())
        reading.set()
        assert release_read.wait(10)
        return original_apps(search_id)

    class UnusedAnalyzer:
        def __init__(self, _key):
            pass

        def close(self):
            pass

    bridge.importer.analyzer_factory = UnusedAnalyzer
    monkeypatch.setattr(bridge.importer, "stage_message", stage)
    monkeypatch.setattr(tracker, "applications", apps)
    bridge.messageChanged.connect(lambda: progress_threads.append(QThread.currentThread()))
    bridge._scan_plan = {
        "search_id": search,
        "start": "2026-09-01T00:00:00Z",
        "end": "2026-10-01T00:00:00Z",
        "candidates": {str(account_id): [f"new-{index}" for index in range(2610)]},
    }
    QQuickStyle.setStyle("Basic")
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda items: warnings.extend(item.toString() for item in items))
    engine.rootContext().setContextProperty("backend", bridge)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parents[1] / "src/job_tracker/ui/Main.qml")))
    window = engine.rootObjects()[0]
    heartbeat = QTimer()
    ticks = []
    heartbeat.setInterval(10)
    heartbeat.timeout.connect(lambda: ticks.append(True))
    heartbeat.start()

    def click(item):
        point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)

    def walk(item):
        yield item
        for child in item.childItems():
            yield from walk(child)

    try:
        qtbot.wait(80)
        bridge.startHistory(1)
        qtbot.waitUntil(staged.is_set, timeout=3000)
        bridge.refreshWhileBusy()
        qtbot.waitUntil(reading.is_set, timeout=3000)
        # Both workers are blocked. The UI must continue handling real input.
        click(
            next(item for item in walk(window.contentItem()) if item.objectName() == "navigation-2")
        )
        qtbot.waitUntil(lambda: window.property("page") == 2)
        cards = [
            item
            for item in walk(window.contentItem())
            if item.objectName().startswith("reviewCard-")
        ]
        assert 0 < len(cards) < 103, "Only visible review cards should be instantiated"
        header = next(
            item
            for item in walk(window.contentItem())
            if item.objectName().startswith("reviewHeader-")
        )
        click(header)
        qtbot.waitUntil(lambda: cards[0].property("expanded"))
        field = window.findChild(QObject, "reviewFilter")
        field.forceActiveFocus()
        for key in (Qt.Key_K, Qt.Key_I, Qt.Key_W, Qt.Key_I):
            QTest.keyClick(window, key)
        qtbot.waitUntil(lambda: field.property("text") == "kiwi")
        qtbot.waitUntil(lambda: len(ticks) >= 5)
        click(window.findChild(QObject, "pauseScanButton"))
        assert bridge.importer.cancelled.is_set()
        assert bridge.busy  # UI input was handled before either worker was released.
        assert stage_threads[0] != qapp.thread() and read_threads[0] != qapp.thread()
        assert all(thread == qapp.thread() for thread in progress_threads)
        release_stage.set()
        release_read.set()
        qtbot.waitUntil(lambda: not bridge.busy, timeout=3000)
        qtbot.waitUntil(
            lambda: any(item["state"] == "paused" for item in bridge.scans), timeout=3000
        )
        with tracker.db.sessions() as session:
            assert len(list(session.scalars(select(Job).where(Job.state == "pending")))) == 1
        assert len(bridge.applications) == 408 and len(bridge.reviews) == 103
        assert not warnings, "\n".join(warnings)
    finally:
        release_stage.set()
        release_read.set()
        heartbeat.stop()
        window.close()
        bridge.stop()
        engine.deleteLater()
        qapp.processEvents()


def test_startup_recovers_interrupted_scan_without_touching_records(tracker):
    search = tracker.create_search("Recovery")
    app = tracker.save_application(search, {"company": "Company", "role": "Developer"})
    with tracker.db.sessions.begin() as session:
        session.add_all(
            [
                Scan(
                    search_id=search,
                    start_at="2026-09-01",
                    end_at="2026-10-01",
                    budget=1,
                    spent=0.25,
                    state=state,
                )
                for state in ("running", "completed")
            ]
        )
    tracker.recover_interrupted_scans()
    tracker.recover_interrupted_scans()  # Safe on each startup; no automatic paid resume.
    with tracker.db.sessions() as session:
        scans = list(session.scalars(select(Scan).order_by(Scan.id)))
        assert [scan.state for scan in scans] == ["paused", "completed"]
        assert scans[0].spent == 0.25 and "Resume" in scans[0].error
    assert tracker.applications(search)[0]["id"] == app


def test_stale_refresh_cannot_undo_theme_or_lose_new_key(qapp, qtbot, tracker, monkeypatch):
    vault = Credentials()
    vault.get = lambda name: vault.memory.get(name, "")
    bridge = Bridge(tracker, vault, onboarding=False)
    entered, release = Event(), Event()
    original = tracker.applications

    def delayed(search_id):
        entered.set()
        assert release.wait(10)
        return original(search_id)

    monkeypatch.setattr(tracker, "applications", delayed)
    try:
        vault.save("openai", "synthetic-key", persist=False)
        bridge.requestRefresh(credentials=True)
        qtbot.waitUntil(entered.is_set)
        bridge.setDarkMode(True)
        assert bridge.darkMode
        release.set()
        qtbot.waitUntil(lambda: bridge.apiReady and bridge.darkMode, timeout=3000)
        assert tracker.get_setting("theme") == "dark"
    finally:
        release.set()
        bridge.stop()


def test_ui_properties_never_read_sqlite_or_credential_store(qapp, tracker, monkeypatch):
    vault = Credentials()
    vault.get = lambda _name: ""
    bridge = Bridge(tracker, vault, onboarding=False)

    def forbidden(*_args):
        raise AssertionError("A QML getter performed blocking I/O on the GUI thread")

    monkeypatch.setattr(vault, "get", forbidden)
    monkeypatch.setattr(tracker, "get_setting", forbidden)
    try:
        assert not bridge.apiReady and not bridge.googleConfigured
        assert not bridge.aiEnabled and not bridge.darkMode
        assert bridge.syncBudget == "0.25" and bridge.dailyBudget == "1.00"
        assert bridge.microsoftClient == ""
    finally:
        bridge.stop()


def test_retry_backoff_keeps_gui_interactive_and_pause_interrupts_wait(
    qapp, qtbot, tracker, monkeypatch
):
    class UnavailableAnalyzer(FakeAnalyzer):
        dispatches = 0

        def classify(self, message, bill):
            bill("classify", "gpt-6-luna", 0.01)
            type(self).dispatches += 1
            raise api_error()

    vault = Credentials()
    vault.memory.update({"openai": "synthetic-key", "mailbox": "synthetic-token"})
    vault.get = lambda name: vault.memory.get(name, "")
    register(tracker, "gmail", "candidate@example.org", "mailbox")
    bridge = Bridge(tracker, vault, onboarding=False)
    bridge.timer.stop()
    bridge.importer.analyzer_factory = UnavailableAnalyzer
    bridge.importer.mailbox_factory = FakeMailbox
    plan = bridge.importer.preview("2026-09-01T00:00:00Z", "2026-11-01T00:00:00Z")
    bridge._scan_plan = plan | {"search_id": bridge.selectedSearch}
    monkeypatch.setattr("job_tracker.worker.retry_delay", lambda _error, _attempt: 30)
    QQuickStyle.setStyle("Basic")
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", bridge)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parents[1] / "src/job_tracker/ui/Main.qml")))
    window = engine.rootObjects()[0]

    def walk(item):
        yield item
        for child in item.childItems():
            yield from walk(child)

    def click(item):
        point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)

    try:
        qtbot.wait(80)
        bridge.startHistory(1)
        qtbot.waitUntil(lambda: "Retrying OpenAI classification" in bridge.message, timeout=3000)
        assert bridge.busy and UnavailableAnalyzer.dispatches == 1
        # A real 30-second worker wait must not block navigation or Pause input.
        click(
            next(item for item in walk(window.contentItem()) if item.objectName() == "navigation-1")
        )
        qtbot.waitUntil(lambda: window.property("page") == 1)
        click(window.findChild(QObject, "pauseScanButton"))
        qtbot.waitUntil(lambda: not bridge.busy, timeout=2000)
        assert UnavailableAnalyzer.dispatches == 1 and bridge.importer.cancelled.is_set()
        assert "paused" in bridge.message and "0.0100" in bridge.message
    finally:
        bridge.importer.cancelled.set()
        window.close()
        bridge.stop()
        engine.deleteLater()
        qapp.processEvents()
