"""Initial desktop schema.

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Explicit schema stays stable when the application's models evolve.
    op.create_table(
        "job_searches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("start_date", sa.String, nullable=False),
        sa.Column("end_date", sa.String, nullable=False),
        sa.Column("archived", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
    )
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("search_id", sa.Integer, sa.ForeignKey("job_searches.id"), nullable=False),
        *[
            sa.Column(name, sa.String, nullable=False)
            for name in (
                "company",
                "role",
                "requisition_id",
                "applied_on",
                "stage",
                "outcome",
                "notes",
                "status_at",
                "created_at",
                "updated_at",
            )
        ],
        sa.Column("manual_override", sa.Boolean, nullable=False),
    )
    for name in ("search_id", "company", "requisition_id"):
        op.create_index(f"ix_applications_{name}", "applications", [name])
    op.create_table(
        "email_accounts",
        sa.Column("id", sa.Integer, primary_key=True),
        *[
            sa.Column(name, sa.String, nullable=False)
            for name in ("provider", "address", "credential_ref", "client_id", "last_sync")
        ],
        sa.UniqueConstraint("provider", "address"),
    )
    op.create_table(
        "email_messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("email_accounts.id"), nullable=False),
        *[
            sa.Column(name, sa.String, nullable=False)
            for name in (
                "provider_id",
                "thread_id",
                "sender",
                "subject",
                "body",
                "received_at",
                "state",
                "result_json",
            )
        ],
        sa.UniqueConstraint("account_id", "provider_id"),
    )
    op.create_table(
        "application_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("message_id", sa.Integer, sa.ForeignKey("email_messages.id")),
        *[
            sa.Column(name, sa.String, nullable=False)
            for name in ("kind", "evidence", "effective_at", "created_at")
        ],
        sa.UniqueConstraint("application_id", "message_id", "kind"),
    )
    op.create_index(
        "ix_application_events_application_id", "application_events", ["application_id"]
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("event_id", sa.Integer, sa.ForeignKey("application_events.id")),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("due_at", sa.String, nullable=False),
        sa.Column("completed", sa.Boolean, nullable=False),
    )
    op.create_table(
        "history_scan_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("search_id", sa.Integer, sa.ForeignKey("job_searches.id"), nullable=False),
        *[
            sa.Column(name, sa.String, nullable=False)
            for name in ("start_at", "end_at", "state", "created_at")
        ],
        sa.Column("budget", sa.Float, nullable=False),
        sa.Column("spent", sa.Float, nullable=False),
    )
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("message_id", sa.Integer, sa.ForeignKey("email_messages.id"), nullable=False),
        sa.Column("search_id", sa.Integer, sa.ForeignKey("job_searches.id"), nullable=False),
        sa.Column("scan_id", sa.Integer, sa.ForeignKey("history_scan_runs.id"), nullable=False),
        *[sa.Column(name, sa.String, nullable=False) for name in ("state", "retry_at", "error")],
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.UniqueConstraint("message_id", "search_id"),
    )
    op.create_table(
        "review_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("job_id", sa.Integer, sa.ForeignKey("processing_jobs.id"), nullable=False),
        sa.Column("search_id", sa.Integer, sa.ForeignKey("job_searches.id"), nullable=False),
        *[
            sa.Column(name, sa.String, nullable=False)
            for name in ("proposed_json", "reason", "state")
        ],
        sa.UniqueConstraint("job_id"),
    )
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scan_id", sa.Integer, sa.ForeignKey("history_scan_runs.id"), nullable=False),
        sa.Column("message_id", sa.Integer, sa.ForeignKey("email_messages.id"), nullable=False),
        *[
            sa.Column(name, sa.String, nullable=False)
            for name in ("operation", "model", "created_at")
        ],
        sa.Column("input_tokens", sa.Integer, nullable=False),
        sa.Column("output_tokens", sa.Integer, nullable=False),
        sa.Column("cost", sa.Float, nullable=False),
    )
    op.create_table(
        "settings",
        sa.Column("key", sa.String, primary_key=True),
        sa.Column("value", sa.String, nullable=False),
    )


def downgrade():
    for name in (
        "settings",
        "ai_usage",
        "review_items",
        "processing_jobs",
        "history_scan_runs",
        "tasks",
        "application_events",
        "email_messages",
        "email_accounts",
        "applications",
        "job_searches",
    ):
        op.drop_table(name)
