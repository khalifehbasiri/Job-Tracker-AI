"""Installed-app registration metadata; user tokens and API keys never belong here."""

import json
from pathlib import Path

from job_tracker.errors import UserFacingError

MICROSOFT_CLIENT_ID = "REPLACE_WITH_YOUR_OAUTH_CLIENT_ID"
GOOGLE_CLIENT_FILE = Path(__file__).with_name("google_desktop_oauth.json")
HOMEPAGE = "https://github.com/khalifehbasiri/Job-Tracker-AI"
PRIVACY_URL = HOMEPAGE + "/blob/main/PRIVACY.md"


def google_desktop_client(config: dict) -> dict:
    """Keep only native-client metadata, pin endpoints, exclude tokens/other credentials."""
    installed = config.get("installed") if isinstance(config, dict) else None
    if not isinstance(installed, dict):
        raise UserFacingError("Choose a Google OAuth client JSON for a Desktop application.")
    client_id, client_secret = installed.get("client_id"), installed.get("client_secret")
    if (
        not isinstance(client_id, str)
        or not client_id.endswith(".apps.googleusercontent.com")
        or len(client_id) > 1000
        or not isinstance(client_secret, str)
        or not 0 < len(client_secret) <= 1000
    ):
        raise UserFacingError("The Google Desktop OAuth client configuration is incomplete.")
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def bundled_google_client() -> dict | None:
    if not GOOGLE_CLIENT_FILE.exists():
        return None
    return google_desktop_client(json.loads(GOOGLE_CLIENT_FILE.read_text(encoding="utf-8")))
