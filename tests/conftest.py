import pytest

from job_tracker.db import Database
from job_tracker.services import Tracker


@pytest.fixture
def tracker(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    yield Tracker(db)
    db.close()
