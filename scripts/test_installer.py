"""Exercise an installer only when there is no existing registered installation."""

import argparse
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous-installer", type=Path)
    parser.add_argument("--check-shortcuts", action="store_true")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("This check requires Windows.")
    import winreg

    key = (
        "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\"
        "{F2868D6B-FC90-40CF-AE49-73B644695C6D}_is1"
    )
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key):
            raise SystemExit("An installation already exists; use an isolated Windows account.")
    except FileNotFoundError:
        pass
    target = (ROOT / "artifacts/installer-smoke/app").resolve()
    if not target.is_relative_to(ROOT / "artifacts"):
        raise SystemExit("Installer test path is outside the workspace artifacts folder.")
    target.parent.mkdir(parents=True, exist_ok=True)
    database = target.parent / "retained.sqlite3"
    installer = ROOT / "dist/release/Job-Tracker-AI-Setup.exe"

    def install(package=installer):
        subprocess.run(
            [
                str(package),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                *([] if args.check_shortcuts else ["/NOICONS"]),
                f"/DIR={target}",
                f"/LOG={target.parent / 'install.log'}",
            ],
            check=True,
            timeout=120,
        )

    def launch():
        image = target.parent / "installed.png"
        image.unlink(missing_ok=True)
        subprocess.run(
            [
                str(target / "Job-Tracker-AI.exe"),
                "--demo",
                "--database",
                str(database),
                "--screenshot",
                str(target.parent / "installed.png"),
            ],
            check=True,
            timeout=60,
            env=os.environ | {"QT_QUICK_BACKEND": "software"},
        )
        assert image.exists() and image.stat().st_size > 1000

    install(args.previous_installer or installer)
    try:
        assert (target / "Job-Tracker-AI.exe").exists()
        launch()
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE applications SET notes = 'upgrade-preservation-marker'")
        install()
        guide = target / "Setup guide/setup.html"
        assert guide.is_file() and "F1" in guide.read_text(encoding="utf-8")
        if args.check_shortcuts:
            shortcuts = (
                Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Job Tracker AI"
            )
            assert (shortcuts / "Job Tracker AI.lnk").exists()
            assert (shortcuts / "Job Tracker AI setup guide.lnk").exists()
        launch()
        with sqlite3.connect(database) as connection:
            assert connection.execute("SELECT count(*) FROM applications").fetchone()[0] == 5
            assert (
                connection.execute(
                    "SELECT count(*) FROM applications WHERE notes = 'upgrade-preservation-marker'"
                ).fetchone()[0]
                == 5
            )
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        subprocess.run(
            [str(target / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
            check=True,
            timeout=120,
        )
    assert database.exists()
    assert not (target / "Job-Tracker-AI.exe").exists()
    upgrade = "cross-version" if args.previous_installer else "same-version"
    print(f"Install, {upgrade} upgrade, launch, and uninstall passed; records preserved.")


if __name__ == "__main__":
    main()
