from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    MetaData,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

URL_MAX_LENGTH = 2048

metadata = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
})


class Base(DeclarativeBase):
    metadata = metadata


class Url(Base):
    __tablename__ = "urls"
    __table_args__ = (
        CheckConstraint(
            f"length(original_url) <= {URL_MAX_LENGTH}",
            name="original_url_length",
        ),
        Index("ix_urls_created_by", "created_by"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str | None] = mapped_column(String(254), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
