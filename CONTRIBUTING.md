# Contributing

Use Python 3.13 and `uv sync --locked`. The entry point is `uv run job-tracker`; `--demo` uses a separate fictional-data database. New runtime dependencies should update both `pyproject.toml` and `uv.lock`.

Keep business rules in `domain.py`, `services.py`, and `worker.py`; database schema and migrations in `db.py` and `migrations/`; provider interactions in `email.py` and `ai.py`; and desktop presentation in `ui/`. QML accesses services through the Qt bridge. Network operations belong on the serialized worker, with short database transactions outside network calls.

Group changes into focused commits. Run Ruff lint/format checks and tests before submitting a pull request. Use fake mailboxes and HTTP/API responses in tests, never contributor credentials or paid requests. Behavioral tests should protect meaningful properties such as identity matching, idempotency, search isolation, status chronology, budgets, and credential handling.

Email content is untrusted. Keep models tool-free, validate extracted facts, preserve manual corrections, and route ambiguous application identity to review. Do not add mail-send privileges to the tracker. Never log provider exception text, message bodies, or credentials. Data presented in QML should use plain text.

Schema changes need explicit Alembic migrations. Do not modify a migration already distributed to users. Keep SQLite databases, OAuth JSON, workbooks, and API keys out of commits and issue attachments. See [privacy](PRIVACY.md) and [security reporting](SECURITY.md).

CI builds a source distribution and a wheel containing QML and migrations. A wheel still requires Python and dependencies; it is not a standalone Windows installer. Signed binary packaging and third-party notices are a separate release milestone.
