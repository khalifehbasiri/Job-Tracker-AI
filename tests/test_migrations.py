from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

import job_tracker.db as db_module
from job_tracker.db import Database, Scan


def test_upgrade_preserves_paused_scan_and_search(tmp_path):
    path = tmp_path / "existing.sqlite3"
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    config = Config()
    config.set_main_option("script_location", str(Path(db_module.__file__).parent / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001")
        connection.execute(
            text(
                "INSERT INTO job_searches "
                "(id, name, start_date, end_date, archived, created_at) "
                "VALUES (1, 'Existing search', '', '', 0, '2026-10-01T00:00:00Z')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO history_scan_runs "
                "(id, search_id, start_at, end_at, budget, spent, state, created_at) "
                "VALUES (1, 1, '2026-09-01T00:00:00Z', '2026-10-01T00:00:00Z', "
                "1, 0, 'paused', '2026-10-01T00:00:00Z')"
            )
        )
        for application_id, applied_on, kind in [
            (1, "", "application"),
            (2, "", "rejection"),
            (3, "2026-08-01", "application"),
        ]:
            connection.execute(
                text("""
                INSERT INTO applications
                (id, search_id, company, role, requisition_id, applied_on, stage, outcome,
                 notes, manual_override, status_at, created_at, updated_at)
                VALUES (:id, 1, 'Company', 'Engineer', '', :applied, 'Applied', 'Active',
                        '', 0, '2026-10-01T00:00:00Z', '2026-10-01T00:00:00Z',
                        '2026-10-01T00:00:00Z')
            """),
                {"id": application_id, "applied": applied_on},
            )
            connection.execute(
                text("""
                INSERT INTO application_events
                (application_id, kind, evidence, effective_at, created_at)
                VALUES (:id, :kind, '', '2026-09-20T12:00:00+00:00', '2026-10-01T00:00:00Z')
            """),
                {"id": application_id, "kind": kind},
            )
    engine.dispose()
    db = Database(path)
    try:
        with db.sessions() as session:
            scan = session.get(Scan, 1)
            assert scan.state == "paused" and scan.error == ""
            assert scan.budget == 1 and scan.spent == 0
            assert not scan.hidden
            assert session.execute(
                text("SELECT applied_on FROM applications ORDER BY id")
            ).scalars().all() == ["2026-09-20", "", "2026-08-01"]
            assert (
                session.execute(text("select name from job_searches where id=1")).scalar()
                == "Existing search"
            )
    finally:
        db.close()
