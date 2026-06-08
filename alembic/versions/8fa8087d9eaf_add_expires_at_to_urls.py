"""add expires_at to urls

Revision ID: 8fa8087d9eaf
Revises: 04ea58b4eee9
Create Date: 2026-06-08 01:54:39.714342

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8fa8087d9eaf"
down_revision: Union[str, Sequence[str], None] = "04ea58b4eee9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "urls",
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(op.f("ix_urls_expires_at"), "urls", ["expires_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_urls_expires_at"), table_name="urls")
    op.drop_column("urls", "expires_at")
