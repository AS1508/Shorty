"""add deleted_at to urls

Revision ID: f11a93647e5b
Revises: 8fa8087d9eaf
Create Date: 2026-06-14 02:15:26.528249

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f11a93647e5b'
down_revision: Union[str, Sequence[str], None] = '8fa8087d9eaf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "urls",
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(op.f("ix_urls_deleted_at"), "urls", ["deleted_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_urls_deleted_at"), table_name="urls")
    op.drop_column("urls", "deleted_at")
