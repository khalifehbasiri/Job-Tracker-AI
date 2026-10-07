"""Desktop entry point and a deterministic screenshot/smoke mode."""

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from job_tracker.credentials import Credentials
from job_tracker.db import Database
from job_tracker.services import Tracker
from job_tracker.ui.bridge import Bridge


def main():
    parser = argparse.ArgumentParser(description="Job Tracker AI desktop")
    parser.add_argument("--database", type=Path, help="Use an alternate local SQLite database")
    parser.add_argument(
        "--demo", action="store_true", help="Seed fictional records in an isolated demo DB"
    )
    parser.add_argument("--screenshot", type=Path, help="Save a UI screenshot, then exit")
    args = parser.parse_args()
    QQuickStyle.setStyle("Basic")
    app = QApplication(sys.argv[:1])
    if sys.platform == "win32":
        import os

        fonts = Path(os.environ.get("SystemRoot", "C:/Windows")) / "Fonts"
        for name in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
            if (fonts / name).exists():
                QFontDatabase.addApplicationFont(str(fonts / name))
    app.setApplicationName("JobTrackerAI")
    app.setOrganizationName("JobTrackerAI")
    if args.demo and args.database is None:
        from platformdirs import user_data_path

        args.database = user_data_path("JobTrackerAI", appauthor=False) / "demo.sqlite3"
    db = Database(args.database)
    tracker = Tracker(db)
    if args.demo and not tracker.searches():
        search = tracker.create_search("2026 · The next chapter", "2026-06-01", "2026-12-31")
        for company, role, stage, outcome in [
            ("Northstar Labs", "Software Engineering Intern", "Interview", "Active"),
            ("Fern Technologies", "Python Developer", "Assessment", "Active"),
            ("Orbit Studio", "Junior Software Engineer", "Applied", "Active"),
            ("Maple Systems", "Backend Engineering Co-op", "Offer", "Active"),
            ("Harbor Analytics", "Data Engineering Intern", "Applied", "Rejected"),
        ]:
            tracker.save_application(
                search,
                {
                    "company": company,
                    "role": role,
                    "stage": stage,
                    "outcome": outcome,
                    "applied_on": "2026-10-01",
                },
            )
        tracker.create_search("2025 · Co-op search", "2025-01-01", "2025-12-31")
        tracker.set_setting("selected_search", str(search))
    bridge = Bridge(tracker, Credentials())
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", bridge)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent / "ui" / "Main.qml")))
    if not engine.rootObjects():
        db.close()
        return 1
    window = engine.rootObjects()[0]
    if not isinstance(window, QQuickWindow):
        raise RuntimeError("The desktop root must be a Qt Quick window.")
    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable() and not args.screenshot:
        image = QPixmap(64, 64)
        image.fill(QColor("#216e62"))
        painter = QPainter(image)
        painter.setPen(QColor("white"))
        painter.drawText(image.rect(), 0x84, "JT")
        painter.end()
        tray = QSystemTrayIcon(QIcon(image), app)
        menu = QMenu()
        show = QAction("Show Job Tracker", menu)
        show.triggered.connect(lambda: (window.show(), window.raise_(), window.requestActivate()))
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(app.quit)
        menu.addAction(show)
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda reason: window.show() if reason == QSystemTrayIcon.DoubleClick else None
        )
        tray.setToolTip("Job Tracker AI")
        tray.show()
        bridge._tray = True
        bridge.changed.emit()
    if args.screenshot:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)

        def capture():
            try:
                success = window.grabWindow().save(str(args.screenshot))
                print("Screenshot saved" if success else "Screenshot failed")
                app.exit(0 if success else 1)
            except Exception:
                app.exit(1)

        QTimer.singleShot(1200, capture)
    app.aboutToQuit.connect(bridge.stop)
    result = app.exec()
    if tray:
        tray.hide()
    # Destroy QML bindings while their backend is still alive.
    engine.deleteLater()
    app.processEvents()
    db.close()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
