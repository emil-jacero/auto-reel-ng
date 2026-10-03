"""job-kind: kind column and a per-kind unique-active index

Revision ID: c4a1d7e9b230
Revises: 505f2d2c5ca1
Create Date: 2026-10-03 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4a1d7e9b230"
down_revision: Union[str, Sequence[str], None] = "505f2d2c5ca1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACTIVE = sa.text("status IN ('queued', 'running')")


def upgrade() -> None:
    """Upgrade schema.

    The server default backfills every existing row to ``render`` (no table rewrite on
    PostgreSQL 11+). The unique-active index is swapped for one that also keys on
    ``kind``; the swap runs in this revision's one transaction, so there is no moment
    without protection, and it cannot fail on data: the old key is a strict subset of
    the new one, so every existing row already satisfies it.
    """
    op.add_column(
        "jobs",
        sa.Column("kind", sa.Text(), nullable=False, server_default="render"),
    )
    op.drop_index("ux_jobs_active_identity", table_name="jobs")
    op.create_index(
        "ux_jobs_active_identity",
        "jobs",
        ["project_root", "event_dir", "kind"],
        unique=True,
        postgresql_where=_ACTIVE,
    )


def downgrade() -> None:
    """Downgrade schema.

    Rows whose ``kind`` is not ``render`` are deleted: a render and a proxy job active
    for one event would violate the narrower index being restored. That is safe because
    the table is derived, rebuildable state (Principle II); what a non-render job made
    (for example the proxy cache) lives on disk and is untouched.
    """
    op.execute("DELETE FROM jobs WHERE kind <> 'render'")
    op.drop_index("ux_jobs_active_identity", table_name="jobs")
    op.drop_column("jobs", "kind")
    op.create_index(
        "ux_jobs_active_identity",
        "jobs",
        ["project_root", "event_dir"],
        unique=True,
        postgresql_where=_ACTIVE,
    )
