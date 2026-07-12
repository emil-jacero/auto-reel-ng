"""job-scheduler columns: cancel_requested, project_root, requeue_count

Revision ID: 8941c65cba0d
Revises: ce3faf27bcfd
Create Date: 2026-07-11 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8941c65cba0d"
down_revision: Union[str, Sequence[str], None] = "ce3faf27bcfd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "jobs",
        sa.Column(
            "cancel_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column("jobs", sa.Column("project_root", sa.Text(), nullable=True))
    op.add_column(
        "jobs", sa.Column("requeue_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.create_index(
        "ux_jobs_active_identity",
        "jobs",
        ["project_root", "event_dir"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ux_jobs_active_identity", table_name="jobs")
    op.drop_column("jobs", "requeue_count")
    op.drop_column("jobs", "project_root")
    op.drop_column("jobs", "cancel_requested")
