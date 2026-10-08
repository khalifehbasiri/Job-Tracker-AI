from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from job_tracker.credentials import Credentials
from job_tracker.ui.bridge import Bridge


def test_offline_guide_opens_bundled_html(qapp, tracker, monkeypatch):
    vault = Credentials()
    vault.get = lambda _name: ""
    bridge = Bridge(tracker, vault, onboarding=False)
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
    try:
        assert bridge.openSetupGuide()
        assert isinstance(opened[0], QUrl) and opened[0].isLocalFile()
        path = Path(opened[0].toLocalFile())
        assert path.is_file() and path.name == "setup.html"
        html = path.read_text(encoding="utf-8")
        assert "F1" in html and "Setup guide/setup.html" in html
        assert "C:/Users/khali" not in html
    finally:
        bridge.stop()


def test_browser_failure_is_reported(qapp, tracker, monkeypatch):
    vault = Credentials()
    vault.get = lambda _name: ""
    bridge = Bridge(tracker, vault, onboarding=False)
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda _url: False)
    try:
        assert not bridge.openSetupGuide()
        assert "Could not open your browser" in bridge.message
        assert "Setup guide folder" in bridge.message
    finally:
        bridge.stop()
