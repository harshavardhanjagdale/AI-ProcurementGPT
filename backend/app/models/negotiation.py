from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class Negotiation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "negotiations"

    rfq_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quotation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("quotations.id", ondelete="RESTRICT"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    original_price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    target_price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    negotiated_price: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    email_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("emails.id", ondelete="SET NULL"), nullable=True
    )
    reply_email_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("emails.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    ai_strategy_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    rfq = relationship("RFQ")
    supplier = relationship("Supplier")
    quotation = relationship("Quotation")
