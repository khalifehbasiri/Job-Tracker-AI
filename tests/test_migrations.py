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
    engine.dispose()
    db = Database(path)
    try:
        with db.sessions() as session:
            scan = session.get(Scan, 1)
            assert scan.state == "paused" and scan.error == ""
            assert scan.budget == 1 and scan.spent == 0
            assert (
                session.execute(text("select name from job_searches where id=1")).scalar()
                == "Existing search"
            )
    finally:
        db.close()
