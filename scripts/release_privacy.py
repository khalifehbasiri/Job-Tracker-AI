"""Reject local records and credential files before packaging a public download."""

import json
import re
from pathlib import Path

SECRET = re.compile(rb"(?<![A-Za-z0-9_-])sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}")
PRIVATE_NAMES = {
    ".env",
    "credentials.json",
    "token.json",
    "google_desktop_oauth.json",
}
PRIVATE_SUFFIXES = {".db", ".xlsx", ".xlsm", ".xls"}


def assert_no_private_data(folder: Path):
    """Scan source/runtime files; matching upstream dependency sources are separate."""
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if (
            name in PRIVATE_NAMES
            or name.startswith((".env.", "client_secret"))
            or ".sqlite" in name
            or path.suffix.lower() in PRIVATE_SUFFIXES
        ):
            raise RuntimeError(f"Private data file cannot be shipped: {path.relative_to(folder)}")
        content = path.read_bytes()
        if content.startswith(b"SQLite format 3\x00") or SECRET.search(content):
            raise RuntimeError(f"Private data cannot be shipped: {path.relative_to(folder)}")
        if path.suffix.lower() != ".json":
            continue
        try:
            data = json.loads(content)
        except (ValueError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if any(data.get(key) for key in ("access_token", "refresh_token", "id_token", "api_key")):
            raise RuntimeError(f"Credentials cannot be shipped: {path.relative_to(folder)}")
        if any(
            isinstance(data.get(key), dict) and data[key].get("client_id")
            for key in ("installed", "web")
        ):
            raise RuntimeError(f"OAuth client cannot be shipped: {path.relative_to(folder)}")
