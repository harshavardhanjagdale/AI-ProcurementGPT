from sqlalchemy import BLOB, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class Supplier(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[float] = mapped_column(Numeric(3, 2), default=0.00, nullable=False)
    avg_delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_tax_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    embedding_vector: Mapped[bytes | None] = mapped_column(BLOB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    categories = relationship("SupplierCategory", back_populates="supplier", lazy="selectin", cascade="all, delete-orphan")
    rfq_suppliers = relationship("RFQSupplier", back_populates="supplier", lazy="selectin")
    quotations = relationship("Quotation", back_populates="supplier", lazy="selectin")
