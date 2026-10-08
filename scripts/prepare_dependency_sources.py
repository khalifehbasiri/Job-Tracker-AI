"""Collect matching, checksum-verified sources and notices for binary distribution."""

import hashlib
import importlib.metadata
import json
import shutil
import tarfile
import zipfile
from pathlib import Path

import httpx
from PySide6.QtCore import qVersion

ROOT = Path(__file__).resolve().parents[1]
QT_VERSION = "6.11.2"


def download(client, url, destination, checksum):
    if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() == checksum:
        return
    temporary = destination.with_suffix(destination.suffix + ".part")
    digest = hashlib.sha256()
    try:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_bytes():
                    digest.update(chunk)
                    output.write(chunk)
        if digest.hexdigest() != checksum:
            raise RuntimeError(f"Source checksum mismatch: {destination.name}")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def collect_notices(archive, target):
    with tarfile.open(archive) as source:
        for member in source:
            parts = Path(member.name).parts
            name = parts[-1].lower() if parts else ""
            license_path = any(part.lower() == "licenses" for part in parts)
            notice = name.startswith(("license", "licence", "copying", "notice", "copyright"))
            if member.isfile() and member.size < 2_000_000 and (license_path or notice):
                # Copy text only; never extract archive-supplied paths or symlinks.
                relative = Path(*parts[1:])
                if relative.is_absolute() or ".." in relative.parts:
                    raise RuntimeError("Invalid source notice path")
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as content:
                    destination.write_bytes(content.read())


def prepare():
    if qVersion() != QT_VERSION or importlib.metadata.version("PySide6") != QT_VERSION:
        raise RuntimeError(
            "Review source archives and bundled Qt modules before changing Qt versions."
        )
    cache = ROOT / "build/dependency-sources"
    cache.mkdir(parents=True, exist_ok=True)
    notices = ROOT / "build/source-notices"
    notices.mkdir(parents=True, exist_ok=True)
    urls = [
        f"https://download.qt.io/official_releases/qt/6.11/{QT_VERSION}/submodules/"
        f"{module}-everywhere-src-{QT_VERSION}.tar.xz"
        for module in ("qtbase", "qtdeclarative", "qtsvg")
    ]
    urls.append(
        f"https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-{QT_VERSION}-src/"
        f"pyside-setup-everywhere-src-{QT_VERSION}.tar.xz"
    )
    manifest = []
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        for url in urls:
            response = client.get(url + ".sha256")
            response.raise_for_status()
            checksum = response.text.split()[0].lower()
            if len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
                raise RuntimeError("Invalid upstream checksum")
            manifest.append({"url": url, "sha256": checksum, "file": url.rsplit("/", 1)[-1]})
        # certifi is MPL-2.0; provide its exact corresponding source as well.
        version = importlib.metadata.version("certifi")
        response = client.get(f"https://pypi.org/pypi/certifi/{version}/json")
        response.raise_for_status()
        sdist = next(item for item in response.json()["urls"] if item["packagetype"] == "sdist")
        if not sdist["url"].startswith("https://files.pythonhosted.org/"):
            raise RuntimeError("Unexpected source host")
        manifest.append(
            {"url": sdist["url"], "sha256": sdist["digests"]["sha256"], "file": sdist["filename"]}
        )
        for item in manifest:
            destination = cache / item["file"]
            download(client, item["url"], destination, item["sha256"])
            collect_notices(destination, notices / item["file"].split("-", 1)[0])
    document = cache / "SOURCE-MANIFEST.json"
    document.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(ROOT / "packaging/third-party-notices.md", cache / "README.md")
    output = cache / "Job-Tracker-AI-Dependency-Sources.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as bundle:
        for item in manifest:
            bundle.write(cache / item["file"], item["file"])
        bundle.write(document, document.name)
        bundle.write(cache / "README.md", "README.md")
    print(f"Prepared matching dependency sources: {output}")
    return output


if __name__ == "__main__":
    prepare()
