from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class RFQItem(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "rfq_items"

    rfq_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    specifications: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), default="units", nullable=False)
    estimated_unit_price: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)

    rfq = relationship("RFQ", back_populates="items")
