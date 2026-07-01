from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class SupplierCategory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "supplier_categories"

    supplier_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)

    supplier = relationship("Supplier", back_populates="categories")
