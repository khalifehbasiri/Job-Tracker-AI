import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/release_privacy.py"
spec = importlib.util.spec_from_file_location("release_privacy", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("tracker.sqlite3", b"records"),
        ("tracker.sqlite3-wal", b"records"),
        ("records.db", b"records"),
        ("applications.xlsx", b"records"),
        ("renamed.data", b"SQLite format 3\x00"),
        (".env", b"secret"),
        ("client_secret_desktop.json", b"{}"),
        ("credentials.json", b"{}"),
        ("token.json", b"{}"),
        ("custom.json", b'{"refresh_token":"fictional-token"}'),
        ("custom.json", b'{"access_token":"fictional-token"}'),
        ("custom.json", b'{"installed":{"client_id":"fictional-client"}}'),
        ("config.txt", b"sk-proj-" + b"fictional" * 8),
    ],
)
def test_release_rejects_private_files(tmp_path, filename, content):
    (tmp_path / filename).write_bytes(content)
    with pytest.raises(RuntimeError, match="cannot be shipped"):
        module.assert_no_private_data(tmp_path)


def test_release_allows_code_and_public_dependencies(tmp_path):
    (tmp_path / "setup.html").write_text("Users supply their own OpenAI API key.")
    (tmp_path / "SOURCE-MANIFEST.json").write_text('{"sources": [{"name": "Qt"}]}')
    (tmp_path / "cacert.pem").write_text("Public certificate authority bundle")
    module.assert_no_private_data(tmp_path)
