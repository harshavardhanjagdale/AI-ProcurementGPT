import math

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateError, NotFoundError
from app.models.supplier import Supplier
from app.models.supplier_category import SupplierCategory
from app.repositories.supplier_repository import SupplierRepository
from app.schemas.supplier import (
    SupplierCreate,
    SupplierListResponse,
    SupplierResponse,
    SupplierUpdate,
)


class SupplierService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SupplierRepository(db)

    async def create_supplier(self, data: SupplierCreate) -> Supplier:
        existing = await self.repo.get_by_email(data.email)
        if existing:
            raise DuplicateError("Supplier", "email", data.email)

        supplier = Supplier(
            name=data.name,
            email=data.email,
            phone=data.phone,
            country=data.country,
            city=data.city,
            address=data.address,
            avg_delivery_days=data.avg_delivery_days,
            notes=data.notes,
        )
        supplier = await self.repo.create(supplier)

        for cat_name in data.categories:
            category = SupplierCategory(
                supplier_id=supplier.id,
                category_name=cat_name,
            )
            self.db.add(category)

        await self.db.flush()
        await self.db.refresh(supplier)
        return supplier

    async def get_supplier(self, supplier_id: str) -> Supplier:
        supplier = await self.repo.get_with_categories(supplier_id)
        if supplier is None:
            raise NotFoundError("Supplier", supplier_id)
        return supplier

    async def list_suppliers(
        self,
        page: int = 1,
        limit: int = 20,
        status: str | None = None,
        country: str | None = None,
        category: str | None = None,
        min_rating: float | None = None,
    ) -> SupplierListResponse:
        skip = (page - 1) * limit

        suppliers = await self.repo.search(
            category=category,
            country=country,
            min_rating=min_rating,
            status=status or "active",
            skip=skip,
            limit=limit,
        )

        total = await self.repo.count_filtered(
            category=category,
            country=country,
            min_rating=min_rating,
            status=status or "active",
        )

        return SupplierListResponse(
            items=[SupplierResponse.model_validate(s) for s in suppliers],
            total=total,
            page=page,
            limit=limit,
            pages=math.ceil(total / limit) if total > 0 else 0,
        )

    async def update_supplier(self, supplier_id: str, data: SupplierUpdate) -> Supplier:
        supplier = await self.repo.get_by_id(supplier_id)
        if supplier is None:
            raise NotFoundError("Supplier", supplier_id)

        update_data = data.model_dump(exclude_unset=True, exclude={"categories"})

        if update_data:
            await self.repo.update_by_id(supplier_id, update_data)

        if data.categories is not None:
            # Replace all categories
            from sqlalchemy import delete
            await self.db.execute(
                delete(SupplierCategory).where(SupplierCategory.supplier_id == supplier_id)
            )
            for cat_name in data.categories:
                self.db.add(SupplierCategory(supplier_id=supplier_id, category_name=cat_name))
            await self.db.flush()

        return await self.repo.get_with_categories(supplier_id)

    async def delete_supplier(self, supplier_id: str) -> bool:
        supplier = await self.repo.get_by_id(supplier_id)
        if supplier is None:
            raise NotFoundError("Supplier", supplier_id)

        await self.repo.update_by_id(supplier_id, {"status": "inactive"})
        return True
