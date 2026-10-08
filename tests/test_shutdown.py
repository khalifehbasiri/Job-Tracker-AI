"""Exercise actual desktop process shutdown without real credentials or API calls."""

import os
import subprocess
import sys

import pytest

from job_tracker.desktop_lock import acquire_database_lock


@pytest.mark.parametrize("tray_available", [False, True])
def test_window_close_exits_and_joins_workers(tmp_path, tray_available):
    database = tmp_path / "shutdown.sqlite3"
    script = tmp_path / "close_desktop.py"
    script.write_text(
        """
import sys

from PySide6.QtCore import QTimer
from PySide6.QtQuick import QQuickWindow
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

import job_tracker.main as desktop
from job_tracker.ui.bridge import Work

desktop.Credentials.get = lambda self, name: self.memory.get(name, "")
tray_available = sys.argv.pop() == "True"
QSystemTrayIcon.isSystemTrayAvailable = lambda: tray_available
original_init = desktop.Bridge.__init__
bridges = []

def initialize(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    bridges.append(self)
    self.vault.memory["openai"] = "fictional-session-key"
    def working():
        assert self.importer.cancelled.wait(10), "Closing did not cancel the worker"
    self.pool.start(Work(working))
    self.read_pool.start(Work(working))
    def close_window():
        window = next(w for w in QApplication.topLevelWindows() if isinstance(w, QQuickWindow))
        assert window.close(), "Window close was rejected"
    QTimer.singleShot(200, close_window)
    # A hidden tray process must fail this test instead of hanging indefinitely.
    QTimer.singleShot(3000, lambda: QApplication.instance().exit(3))

desktop.Bridge.__init__ = initialize
result = desktop.main()
assert result == 0, "Closing the window left the tray process running"
bridge = bridges[0]
assert bridge._closing and bridge.importer.cancelled.is_set()
assert bridge.pool.activeThreadCount() == bridge.read_pool.activeThreadCount() == 0
assert not bridge.timer.isActive() and not bridge.refresh_timer.isActive()
raise SystemExit(result)
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(script), "--demo", "--database", str(database), str(tray_available)],
        capture_output=True,
        text=True,
        timeout=25,
        env=os.environ | {"QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # A new launch/installer must not be blocked by the previous desktop process.
    lock = acquire_database_lock(database)
    lock.unlock()
