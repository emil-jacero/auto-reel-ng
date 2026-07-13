"""change-detection: force column

Revision ID: 505f2d2c5ca1
Revises: 8941c65cba0d
Create Date: 2026-07-12 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "505f2d2c5ca1"
down_revision: Union[str, Sequence[str], None] = "8941c65cba0d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "jobs",
        sa.Column("force", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("jobs", "force")
