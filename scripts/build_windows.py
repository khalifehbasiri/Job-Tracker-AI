"""Build a portable folder, smoke-test it, then optionally create the installer."""

import argparse
import hashlib
import importlib.metadata
import os
import shutil
import sqlite3
import struct
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def dependency_notices():
    target = ROOT / "build/notices"
    target.mkdir(parents=True, exist_ok=True)
    inventory = []
    for dist in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata["Name"]):
        name = dist.metadata["Name"]
        inventory.append(f"{name} {dist.version}")
        for file in dist.files or []:
            if any(word in file.name.lower() for word in ("license", "copying", "notice")):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    destination = target / name / str(file).replace("../", "")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
    (target / "INVENTORY.txt").write_text("\n".join(inventory) + "\n", encoding="utf-8")
    shutil.copyfile(ROOT / "packaging/third-party-notices.md", target / "README.md")


def smoke(bundle):
    # Fictional demo records, no user database or provider network calls.
    artifacts = ROOT / "artifacts/frozen-smoke"
    artifacts.mkdir(parents=True, exist_ok=True)
    database, screenshot = artifacts / "demo.sqlite3", artifacts / "dashboard.png"
    result = subprocess.run(
        [
            str(bundle / "Job-Tracker-AI.exe"),
            "--demo",
            "--database",
            str(database),
            "--screenshot",
            str(screenshot),
        ],
        cwd=artifacts,
        timeout=60,
        env=os.environ | {"QT_QUICK_BACKEND": "software"},
    )
    if result.returncode or not screenshot.exists() or screenshot.stat().st_size < 1000:
        raise RuntimeError("Packaged dashboard smoke test failed.")
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM applications").fetchone()[0] == 5
        assert connection.execute("SELECT count(*) FROM email_accounts").fetchone()[0] == 0
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert (bundle / "_internal/job_tracker/help/setup.html").exists()
    if list(bundle.rglob("google_desktop_oauth.json")):
        raise RuntimeError("OAuth configuration must not be bundled in the preview.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", action="store_true")
    parser.add_argument("--iscc", type=Path)
    args = parser.parse_args()
    if sys.platform != "win32" or struct.calcsize("P") != 8:
        raise SystemExit("Build the Windows x64 bundle with 64-bit Python on Windows.")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    if os.environ.get("GITHUB_REF", "").startswith("refs/tags/"):
        tag = os.environ["GITHUB_REF_NAME"]
        if tag != f"v{version}" and not tag.startswith(f"v{version}-"):
            raise SystemExit("Release tag must match the version in pyproject.toml.")
    run(sys.executable, "scripts/build_help.py")
    dependency_notices()
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "packaging/windows.spec")
    bundle = ROOT / "dist/Job-Tracker-AI"
    smoke(bundle)
    for filename in ("README.md", "PRIVACY.md", "LICENSE"):
        shutil.copyfile(ROOT / filename, bundle / filename)
    shutil.copytree(ROOT / "src/job_tracker/help", bundle / "Setup guide", dirs_exist_ok=True)
    release = ROOT / "dist/release"
    release.mkdir(parents=True, exist_ok=True)
    shutil.make_archive(
        str(release / "Job-Tracker-AI-Windows-x64"),
        "zip",
        root_dir=bundle.parent,
        base_dir=bundle.name,
    )
    outputs = [release / "Job-Tracker-AI-Windows-x64.zip"]
    if args.installer:
        compiler = args.iscc or Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe")
        if not compiler.exists():
            raise SystemExit("Install Inno Setup 6, or pass --iscc with its ISCC.exe path.")
        run(str(compiler), f"/DAppVersion={version}", "packaging/installer.iss")
        outputs.append(release / "Job-Tracker-AI-Setup.exe")
    checksums = ""
    for path in outputs:
        with path.open("rb") as file:
            checksums += f"{hashlib.file_digest(file, 'sha256').hexdigest()}  {path.name}\n"
    (release / "SHA256SUMS.txt").write_text(checksums, encoding="utf-8")
    print("Validated Windows preview outputs:", ", ".join(path.name for path in outputs))


if __name__ == "__main__":
    main()
