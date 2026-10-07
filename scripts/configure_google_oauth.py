"""Generate ignored native OAuth build metadata from a private file or CI secret."""

import argparse
import json
import os
from pathlib import Path

from job_tracker.oauth import GOOGLE_CLIENT_FILE, google_desktop_client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    raw = (
        args.source.read_text(encoding="utf-8")
        if args.source
        else os.environ.get("GOOGLE_DESKTOP_OAUTH_JSON", "")
    )
    if not raw:
        print("No maintained Google desktop client supplied; advanced setup remains available.")
        return
    try:
        config = google_desktop_client(json.loads(raw))
    except (ValueError, TypeError):
        raise SystemExit(
            "Invalid Google Desktop OAuth configuration; no values were logged."
        ) from None
    GOOGLE_CLIENT_FILE.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print("Google native OAuth configuration prepared; user credentials were not included.")


if __name__ == "__main__":
    main()
