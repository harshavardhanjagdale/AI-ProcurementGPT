from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class RFQ(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "rfqs"

    rfq_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_min: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    budget_max: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    delivery_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False, index=True)
    ai_workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_user_input: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="rfqs")
    items = relationship("RFQItem", back_populates="rfq", lazy="selectin", cascade="all, delete-orphan")
    suppliers = relationship("RFQSupplier", back_populates="rfq", lazy="selectin", cascade="all, delete-orphan")
    quotations = relationship("Quotation", back_populates="rfq", lazy="selectin")
    emails = relationship("Email", back_populates="rfq", lazy="selectin")
