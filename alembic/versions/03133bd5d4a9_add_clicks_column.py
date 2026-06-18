"""add clicks column

Revision ID: 03133bd5d4a9
Revises: f11a93647e5b
Create Date: 2026-06-18 11:24:50.141557

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '03133bd5d4a9'
down_revision: Union[str, Sequence[str], None] = 'f11a93647e5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "urls",
        sa.Column("clicks", sa.BigInteger(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("urls", "clicks")
