from sqlalchemy import ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class Quotation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quotations"

    rfq_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    email_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("emails.id", ondelete="SET NULL"), nullable=True
    )
    total_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    tax_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    tax_amount: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    grand_total: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warranty_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    validity_days: Mapped[int | None] = mapped_column(Integer, default=30)
    ai_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    ai_ranking: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_analysis_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="received", nullable=False, index=True)
    raw_ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 0 = original quote; 1, 2, … = revised quotes received after negotiation rounds.
    negotiation_round: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    rfq = relationship("RFQ", back_populates="quotations")
    supplier = relationship("Supplier", back_populates="quotations")
    items = relationship("QuotationItem", back_populates="quotation", lazy="selectin", cascade="all, delete-orphan")
