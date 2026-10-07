"""Retain safe scan diagnostics without changing saved emails or applications."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "history_scan_runs", sa.Column("error", sa.String, nullable=False, server_default="")
    )
    op.create_index("ix_processing_jobs_scan_id", "processing_jobs", ["scan_id"])


def downgrade():
    op.drop_index("ix_processing_jobs_scan_id", "processing_jobs")
    op.drop_column("history_scan_runs", "error")
