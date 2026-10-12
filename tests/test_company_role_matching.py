import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from job_tracker.db import Application, Job, Message, Usage
from job_tracker.email import register
from job_tracker.matching import company_key, role_key
from job_tracker.worker import Importer, match_application


@pytest.mark.parametrize(
    ("company", "role"),
    [
        ("ACME INC.", "Software Engineer"),
        ("Acme Incorporated", "  Software\u00a0Engineer  "),
        ("Acme", "Software\nEngineer"),
    ],
)
def test_company_role_fallback_matches_without_email_requisition(tracker, company, role):
    search = tracker.create_search("2026")
    app_id = tracker.save_application(
        search, {"company": "Acme, Inc.", "role": "Software Engineer", "requisition_id": "REQ-123"}
    )
    with tracker.db.sessions() as session:
        app, reason = match_application(
            session, SimpleNamespace(thread_id=""), {"company": company, "role": role}, search
        )
        assert (app.id, reason) == (app_id, "")


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("Full-Stack Developer", "Full Stack Developer"),
        ("Software Developer – Co-op", "Software Developer - Coop"),
        ("Sr. C++ Developer", "Senior C++ Developer"),
        ("Jr. .NET Developer", "Junior .NET Developer"),
        ("Research &amp; Development Engineer", "Research and Development Engineer"),
    ],
)
def test_role_formatting_equivalents(left, right):
    assert role_key(left) == role_key(right)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("Senior Software Engineer", "Software Engineer"),
        ("Software Engineer - Canada", "Software Engineer - US"),
        ("Software Engineer I", "Software Engineer II"),
        ("C++ Developer", "C# Developer"),
        ("C Developer", "C++ Developer"),
        (".NET Developer", "NET Developer"),
        ("Software Developer Co-op", "Software Developer"),
    ],
)
def test_role_normalization_keeps_meaningful_differences(left, right):
    assert role_key(left) != role_key(right)


def test_normalized_collision_stays_in_review_and_exact_match_still_wins(tracker):
    search = tracker.create_search("2026")
    first = tracker.save_application(search, {"company": "Acme Inc.", "role": "Engineer"})
    tracker.save_application(search, {"company": "Acme Ltd.", "role": "Engineer"})
    with tracker.db.sessions() as session:
        message = SimpleNamespace(thread_id="")
        app, reason = match_application(
            session, message, {"company": "Acme", "role": "Engineer"}, search
        )
        assert app is None and "Multiple" in reason
        app, reason = match_application(
            session, message, {"company": "Acme Inc.", "role": "Engineer"}, search
        )
        assert (app.id, reason) == (first, "")


def test_normalized_fallback_keeps_search_scope_and_id_conflicts(tracker):
    old_search = tracker.create_search("2025")
    search = tracker.create_search("2026")
    tracker.save_application(
        old_search, {"company": "Acme Inc.", "role": "Senior Engineer", "requisition_id": "OLD"}
    )
    message = SimpleNamespace(thread_id="")
    fields = {"company": "Acme", "role": "Sr. Engineer"}
    with tracker.db.sessions() as session:
        assert match_application(session, message, fields, search) == (
            None,
            "No exact application match.",
        )
    tracker.save_application(
        search, {"company": "Acme Inc.", "role": "Senior Engineer", "requisition_id": "OLD"}
    )
    with tracker.db.sessions() as session:
        app, reason = match_application(
            session, message, fields | {"requisition_id": "NEW"}, search
        )
        assert app is None and "conflicts" in reason


def test_company_names_keep_brand_and_subsidiary_words():
    assert company_key("Acme, Inc.") == company_key("ACME Incorporated")
    assert company_key("Acme Canada") != company_key("Acme US")
    assert company_key("Acme Technologies") != company_key("Acme")


def test_normalized_fallback_updates_record_without_creating_duplicate(tracker):
    search = tracker.create_search("2026")
    app_id = tracker.save_application(
        search,
        {"company": "Acme Inc.", "role": "Full-Stack Developer", "requisition_id": "REQ-123"},
    )
    register(tracker, "gmail", "candidate@example.org", "fake")
    importer = Importer(tracker, None)
    scan = importer.create_scan(search, {"start": "2026-09-01", "end": "2026-11-01"}, 1)
    job_id = importer.stage_message(tracker.accounts()[0], "one", scan, search)
    with tracker.db.sessions.begin() as session:
        app = session.get(Application, app_id)
        app.manual_override, app.status_at = False, "2026-09-01T12:00:00Z"
        message = session.get(Message, session.get(Job, job_id).message_id)
        message.state, message.body = "pending", "Please complete your online assessment."
        message.received_at = "2026-10-01T12:00:00Z"
        message.result_json = json.dumps(
            {
                "probability": 0.99,
                "confidence": 0.99,
                "kind": "assessment",
                "extraction": {
                    "company": "Acme",
                    "role": "Full Stack Developer",
                    "evidence": "Please complete your online assessment.",
                },
            }
        )
    importer.process(job_id, None)
    apps = tracker.applications(search)
    assert len(apps) == 1
    assert (apps[0]["id"], apps[0]["stage"]) == (app_id, "Assessment")
    assert not tracker.reviews(search)
    with tracker.db.sessions() as session:
        assert session.scalar(select(Usage.id)) is None
