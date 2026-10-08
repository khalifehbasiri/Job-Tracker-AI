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
        version = (
            tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
            if name.lower().replace("_", "-") == "job-tracker-ai"
            else dist.version
        )
        inventory.append(f"{name} {version}")
        for file in dist.files or []:
            if any(
                word in str(file).lower() for word in ("license", "licence", "copying", "notice")
            ):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    destination = target / name / str(file).replace("../", "")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
    (target / "INVENTORY.txt").write_text("\n".join(inventory) + "\n", encoding="utf-8")
    shutil.copyfile(ROOT / "packaging/third-party-notices.md", target / "README.md")
    shutil.copytree(ROOT / "build/source-notices", target / "upstream", dirs_exist_ok=True)
    shutil.copyfile(
        ROOT / "build/dependency-sources/SOURCE-MANIFEST.json", target / "SOURCE-MANIFEST.json"
    )
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise RuntimeError("The bundled Python runtime license is missing")
    shutil.copyfile(python_license, target / "PYTHON-LICENSE.txt")


def smoke(bundle):
    # Fictional demo records, no user database or provider network calls.
    artifacts = ROOT / "artifacts/frozen-smoke"
    artifacts.mkdir(parents=True, exist_ok=True)
    database, screenshot = artifacts / "demo.sqlite3", artifacts / "dashboard.png"
    screenshot.unlink(missing_ok=True)
    screenshot.with_suffix(".error.txt").unlink(missing_ok=True)
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
        raise RuntimeError(f"Packaged dashboard smoke test failed (exit code {result.returncode}).")
    settings = artifacts / "settings.png"
    settings.unlink(missing_ok=True)
    subprocess.run(
        [
            str(bundle / "Job-Tracker-AI.exe"),
            "--demo",
            "--database",
            str(database),
            "--screenshot",
            str(settings),
            "--screenshot-page",
            "4",
            "--theme",
            "dark",
        ],
        cwd=artifacts,
        timeout=60,
        check=True,
        env=os.environ | {"QT_QUICK_BACKEND": "software"},
    )
    assert settings.exists() and settings.stat().st_size > 1000
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM applications").fetchone()[0] == 5
        assert connection.execute("SELECT count(*) FROM email_accounts").fetchone()[0] == 0
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert (bundle / "_internal/job_tracker/help/setup.html").exists()
    assert (bundle / "_internal/job_tracker/assets/logo.png").exists()
    assert (bundle / "_internal/job_tracker/ui/Theme.qml").exists()
    assert (bundle / "_internal/job_tracker/ui/qmldir").exists()
    if list(bundle.rglob("google_desktop_oauth.json")):
        raise RuntimeError("OAuth configuration must not be bundled in the preview.")
    for unused in (
        "Qt6WebEngineCore.dll",
        "Qt6VirtualKeyboard.dll",
        "Qt6Charts.dll",
        "Qt6Pdf.dll",
        "Qt6Quick3DUtils.dll",
    ):
        if list(bundle.rglob(unused)):
            raise RuntimeError(f"Unused Qt component was bundled: {unused}")
    allowed_qt = {
        "Qt6Core.dll",
        "Qt6Gui.dll",
        "Qt6Network.dll",
        "Qt6OpenGL.dll",
        "Qt6Widgets.dll",
        "Qt6Svg.dll",
        "Qt6Qml.dll",
        "Qt6QmlMeta.dll",
        "Qt6QmlModels.dll",
        "Qt6QmlWorkerScript.dll",
        "Qt6Quick.dll",
        "Qt6QuickLayouts.dll",
        "Qt6QuickTemplates2.dll",
        "Qt6QuickControls2.dll",
        "Qt6QuickControls2Impl.dll",
        "Qt6QuickControls2Basic.dll",
        "Qt6QuickControls2BasicStyleImpl.dll",
    }
    if any(path.name not in allowed_qt for path in bundle.rglob("Qt6*.dll")):
        raise RuntimeError("An unreviewed Qt module was bundled; update the source/license audit.")
    notices = bundle / "_internal/THIRD_PARTY_NOTICES"
    if not list(notices.rglob("LGPL-3.0-only.txt")) or not list(notices.rglob("GPL-3.0-only.txt")):
        raise RuntimeError("Required Qt license texts are missing")


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
    run(sys.executable, "scripts/prepare_dependency_sources.py")
    dependency_notices()
    # Other desktop tools may put incompatible DLLs (for example Poppler's ICU)
    # on PATH. Qt uses Windows' ICU; dependency discovery must prefer System32.
    system = Path(os.environ["SystemRoot"])
    build_env = os.environ | {
        "PATH": os.pathsep.join(
            str(path)
            for path in (
                system / "System32",
                system,
                Path(sys.base_prefix),
                Path(sys.executable).parent,
            )
        )
    }
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "packaging/windows.spec"],
        cwd=ROOT,
        check=True,
        env=build_env,
    )
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
    sources = release / "Job-Tracker-AI-Dependency-Sources.zip"
    shutil.copyfile(ROOT / "build/dependency-sources" / sources.name, sources)
    guide = release / "Job-Tracker-AI-Setup-Guide.html"
    shutil.copyfile(ROOT / "src/job_tracker/help/setup.html", guide)
    outputs = [release / "Job-Tracker-AI-Windows-x64.zip", sources, guide]
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
