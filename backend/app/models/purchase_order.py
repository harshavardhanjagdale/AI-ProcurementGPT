from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class PurchaseOrder(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "purchase_orders"

    po_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    rfq_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rfqs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    supplier_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quotation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("quotations.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    total_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    shipping_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    pdf_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    email_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("emails.id", ondelete="SET NULL"), nullable=True
    )

    user = relationship("User", back_populates="purchase_orders")
    supplier = relationship("Supplier")
    rfq = relationship("RFQ")
    quotation = relationship("Quotation")
    items = relationship("PurchaseOrderItem", back_populates="purchase_order", lazy="selectin", cascade="all, delete-orphan")
