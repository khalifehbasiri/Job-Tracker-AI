"""Record mailbox dates and retain an audit link for redundant emails."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    for column in ("first_email_at", "last_email_at"):
        op.add_column(
            "applications", sa.Column(column, sa.String(), nullable=False, server_default="")
        )
    # SQLite permits a nullable REFERENCES column in ADD COLUMN. This avoids
    # rebuilding processing_jobs while pending review_items reference it.
    op.execute(
        "ALTER TABLE processing_jobs ADD COLUMN filtered_into_message_id "
        "INTEGER REFERENCES email_messages(id)"
    )
    op.add_column(
        "processing_jobs",
        sa.Column("filter_reason", sa.String(), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_processing_jobs_filtered_into_message_id",
        "processing_jobs",
        ["filtered_into_message_id"],
    )
    op.execute("""
        UPDATE applications SET
          first_email_at = COALESCE((
            SELECT min(strftime('%Y-%m-%dT%H:%M:%S+00:00', m.received_at))
            FROM application_events e JOIN email_messages m ON m.id = e.message_id
            WHERE e.application_id = applications.id
          ), ''),
          last_email_at = COALESCE((
            SELECT max(strftime('%Y-%m-%dT%H:%M:%S+00:00', m.received_at))
            FROM application_events e JOIN email_messages m ON m.id = e.message_id
            WHERE e.application_id = applications.id
          ), '')
    """)


def downgrade():
    op.drop_index("ix_processing_jobs_filtered_into_message_id", table_name="processing_jobs")
    op.drop_column("processing_jobs", "filtered_into_message_id")
    op.drop_column("processing_jobs", "filter_reason")
    op.drop_column("applications", "last_email_at")
    op.drop_column("applications", "first_email_at")
