import sqlite3

import pytest
from openpyxl import load_workbook

from job_tracker.domain import project_status
from job_tracker.excel import export_search, import_rows, preview_import


def test_search_isolation_move_and_exports(tracker, tmp_path):
    first = tracker.create_search("2024")
    second = tracker.create_search("2025")
    app = tracker.save_application(first, {"company": "=HYPERLINK(unsafe)", "role": "Developer"})
    assert not tracker.applications(second)
    output = tmp_path / "export.xlsx"
    export_search(tracker, first, output)
    workbook = load_workbook(output)
    assert workbook["Applications"]["A2"].data_type == "s"
    assert len(workbook["Events"]["A"]) == 2
    workbook.close()
    preview = preview_import(output)
    mapping = {
        "company": 0,
        "role": 1,
        "applied_on": 2,
        "stage": 3,
        "outcome": 4,
        "requisition_id": 5,
        "notes": 6,
    }
    assert import_rows(tracker, second, preview, mapping) == (1, 0)
    assert import_rows(tracker, second, preview, mapping) == (0, 1)
    tracker.move_application(app, second)
    assert not tracker.applications(first)


def test_invalid_import_is_atomic(tracker):
    search = tracker.create_search("Search")
    preview = {"rows": [["Company", "Engineer", "2026-10-01"], ["Other", "", "bad-date"]]}
    with pytest.raises(ValueError):
        import_rows(tracker, search, preview, {"company": 0, "role": 1, "applied_on": 2})
    assert tracker.applications(search) == []


def test_manual_override_and_validation(tracker):
    search = tracker.create_search("Search")
    app = tracker.save_application(search, {"company": "Company", "role": "Engineer"})
    tracker.save_application(
        search, {"company": "Company", "role": "Engineer", "stage": "Interview"}, app
    )
    assert tracker.applications(search)[0]["manual_override"]
    with pytest.raises(ValueError):
        tracker.create_search("Search", "2026-12-31", "2026-01-01")
    assert project_status("Interview", "Active", "application") == ("Interview", "Active")
    assert project_status("Interview", "Rejected", "offer") == ("Interview", "Rejected")


def test_backup_contains_committed_records(tracker, tmp_path):
    tracker.create_search("Backup search")
    backup = tmp_path / "backup.sqlite3"
    tracker.backup(backup)
    with sqlite3.connect(backup) as connection:
        assert connection.execute("select name from job_searches").fetchone()[0] == "Backup search"
