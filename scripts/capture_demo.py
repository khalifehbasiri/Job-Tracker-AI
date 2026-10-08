"""Capture README demos using fictional data, with no credentials or API calls."""

import json
import os
import subprocess
import sys
from pathlib import Path

from job_tracker.db import Account, Database, Job, Message, Review, Scan
from job_tracker.excel import export_search
from job_tracker.services import Tracker

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts/readme-demo"
IMAGES = ROOT / "docs/images"


def capture(database, name, page, theme):
    subprocess.run(
        [
            sys.executable,
            "-m",
            "job_tracker.main",
            "--demo",
            "--database",
            str(database),
            "--screenshot",
            str(IMAGES / name),
            "--screenshot-page",
            str(page),
            "--theme",
            theme,
        ],
        cwd=ROOT,
        check=True,
        timeout=60,
        env=os.environ | {"QT_QUICK_BACKEND": "software"},
    )


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    IMAGES.mkdir(parents=True, exist_ok=True)
    # Never operate on an existing user database, even if run repeatedly.
    database = ARTIFACTS / "fictional.sqlite3"
    database.unlink(missing_ok=True)
    capture(database, "dashboard.png", 0, "light")  # Seeds the standard five demo records.
    db = Database(database)
    tracker = Tracker(db)
    search = int(tracker.get_setting("selected_search"))
    with db.sessions.begin() as session:
        account = Account(provider="gmail", address="demo-candidate@example.org", credential_ref="")
        session.add(account)
        scan = Scan(
            search_id=search,
            start_at="2026-09-01T00:00:00+00:00",
            end_at="2026-10-08T00:00:00+00:00",
            budget=1,
            spent=0.12,
            state="completed",
        )
        session.add(scan)
        session.flush()
        for index, (subject, sender, company, role, body) in enumerate(
            [
                (
                    "Your next conversation at Northstar Labs",
                    "careers@northstar.example.org",
                    "Northstar Labs",
                    "Software Engineering Intern",
                    "Hi Candidate,\n\nWe would like to discuss an engineering role with you. "
                    "Please confirm which of your applications this invitation relates to.\n\n"
                    "This is fictional demonstration text.",
                ),
                (
                    "An update on your engineering application",
                    "talent@fern.example.org",
                    "Fern Technologies",
                    None,
                    "Hi Candidate,\n\nThank you for your interest. We have an update about your "
                    "application. The role is not identified in this fictional email.",
                ),
            ]
        ):
            message = Message(
                account_id=account.id,
                provider_id=f"fictional-{index}",
                sender=sender,
                subject=subject,
                body=body,
                received_at="2026-10-05T12:00:00+00:00",
            )
            session.add(message)
            session.flush()
            job = Job(message_id=message.id, search_id=search, scan_id=scan.id, state="review")
            session.add(job)
            session.flush()
            session.add(
                Review(
                    job_id=job.id,
                    search_id=search,
                    reason="The classification needs your confirmation.",
                    proposed_json=json.dumps(
                        {
                            "kind": "interview" if index == 0 else "other",
                            "extraction": {"company": company, "role": role},
                        }
                    ),
                )
            )
    export_search(tracker, search, ARTIFACTS / "fictional-search.xlsx")
    db.close()
    for name, page, theme in [
        ("dashboard.png", 0, "light"),
        ("dashboard-dark.png", 0, "dark"),
        ("applications.png", 1, "light"),
        ("review-inbox.png", 2, "light"),
        ("email-history.png", 3, "light"),
        ("settings-dark.png", 4, "dark"),
    ]:
        capture(database, name, page, theme)
    print("Fictional demo images and Excel snapshot captured; no API calls were made.")


if __name__ == "__main__":
    main()
