"""Hide import history without deleting data; repair missing confirmation dates."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "history_scan_runs",
        sa.Column("hidden", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    # Existing confirmations provide trustworthy email dates without another AI call.
    # Rejections, interviews and manual events must never infer an applied date.
    op.execute("""
        UPDATE applications SET applied_on = (
            SELECT min(substr(effective_at, 1, 10)) FROM application_events
            WHERE application_id = applications.id AND kind = 'application'
        ) WHERE applied_on = '' AND EXISTS (
            SELECT 1 FROM application_events
            WHERE application_id = applications.id AND kind = 'application'
        )
    """)


def downgrade():
    op.drop_column("history_scan_runs", "hidden")
