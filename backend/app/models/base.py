import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def generate_uuid() -> str:
    return str(uuid.uuid4())


# Indian Standard Time (IST) is UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))


def ist_now() -> datetime:
    """Get current time in Indian Standard Time (IST/UTC+5:30)."""
    return datetime.now(IST)


def utc_now() -> datetime:
    """Get current time in UTC (for backward compatibility if needed)."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ist_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ist_now, onupdate=ist_now, nullable=False
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
