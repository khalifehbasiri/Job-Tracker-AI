"""Local SQLite persistence and versioned migrations."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from platformdirs import user_data_path
from sqlalchemy import ForeignKey, String, UniqueConstraint, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from job_tracker.domain import now


class Base(DeclarativeBase):
    pass


class Search(Base):
    __tablename__ = "job_searches"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[str] = mapped_column(default="")
    end_date: Mapped[str] = mapped_column(default="")
    archived: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[str] = mapped_column(default=now)


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("job_searches.id"), index=True)
    company: Mapped[str] = mapped_column(String(200), index=True)
    role: Mapped[str] = mapped_column(String(300))
    requisition_id: Mapped[str] = mapped_column(default="", index=True)
    applied_on: Mapped[str] = mapped_column(default="")
    stage: Mapped[str] = mapped_column(default="Applied")
    outcome: Mapped[str] = mapped_column(default="Active")
    notes: Mapped[str] = mapped_column(default="")
    manual_override: Mapped[bool] = mapped_column(default=False)
    status_at: Mapped[str] = mapped_column(default=now)
    created_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now)


class Account(Base):
    __tablename__ = "email_accounts"
    __table_args__ = (UniqueConstraint("provider", "address"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str]
    address: Mapped[str]
    credential_ref: Mapped[str]
    client_id: Mapped[str] = mapped_column(default="")
    last_sync: Mapped[str] = mapped_column(default="")


class Message(Base):
    __tablename__ = "email_messages"
    __table_args__ = (UniqueConstraint("account_id", "provider_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("email_accounts.id"))
    provider_id: Mapped[str]
    thread_id: Mapped[str] = mapped_column(default="")
    sender: Mapped[str]
    subject: Mapped[str]
    body: Mapped[str]
    received_at: Mapped[str]
    state: Mapped[str] = mapped_column(default="pending")
    result_json: Mapped[str] = mapped_column(default="")


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    __table_args__ = (UniqueConstraint("application_id", "message_id", "kind"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("email_messages.id"))
    kind: Mapped[str]
    evidence: Mapped[str] = mapped_column(default="")
    effective_at: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=now)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    event_id: Mapped[int | None] = mapped_column(ForeignKey("application_events.id"))
    title: Mapped[str]
    due_at: Mapped[str]
    completed: Mapped[bool] = mapped_column(default=False)


class Scan(Base):
    __tablename__ = "history_scan_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("job_searches.id"))
    start_at: Mapped[str]
    end_at: Mapped[str]
    budget: Mapped[float]
    spent: Mapped[float] = mapped_column(default=0.0)
    state: Mapped[str] = mapped_column(default="pending")
    error: Mapped[str] = mapped_column(default="")
    created_at: Mapped[str] = mapped_column(default=now)


class Job(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (UniqueConstraint("message_id", "search_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("email_messages.id"))
    search_id: Mapped[int] = mapped_column(ForeignKey("job_searches.id"))
    scan_id: Mapped[int] = mapped_column(ForeignKey("history_scan_runs.id"))
    state: Mapped[str] = mapped_column(default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    retry_at: Mapped[str] = mapped_column(default="")
    error: Mapped[str] = mapped_column(default="")


class Review(Base):
    __tablename__ = "review_items"
    __table_args__ = (UniqueConstraint("job_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("processing_jobs.id"))
    search_id: Mapped[int] = mapped_column(ForeignKey("job_searches.id"))
    proposed_json: Mapped[str]
    reason: Mapped[str]
    state: Mapped[str] = mapped_column(default="pending")


class Usage(Base):
    __tablename__ = "ai_usage"
    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("history_scan_runs.id"))
    message_id: Mapped[int] = mapped_column(ForeignKey("email_messages.id"))
    operation: Mapped[str]
    model: Mapped[str]
    input_tokens: Mapped[int]
    output_tokens: Mapped[int]
    cost: Mapped[float]
    created_at: Mapped[str] = mapped_column(default=now)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]


class Database:
    def __init__(self, path: Path | None = None):
        self.path = path or user_data_path("JobTrackerAI", appauthor=False) / "tracker.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.path.as_posix()}")

        @event.listens_for(self.engine, "connect")
        def configure(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=5000")

        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
        with self.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

    def close(self):
        self.engine.dispose()
