from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, utc_now


class Email(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "emails"

    rfq_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("rfqs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    supplier_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    email_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    from_address: Mapped[str] = mapped_column(String(255), nullable=False)
    to_address: Mapped[str] = mapped_column(String(255), nullable=False)
    cc_addresses: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    in_reply_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    rfq = relationship("RFQ", back_populates="emails")
    supplier = relationship("Supplier")
    attachments = relationship("EmailAttachment", back_populates="email", lazy="selectin", cascade="all, delete-orphan")
