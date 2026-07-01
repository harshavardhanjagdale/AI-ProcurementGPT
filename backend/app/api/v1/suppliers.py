from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_admin_or_pm, get_admin
from app.database.session import get_db
from app.schemas.supplier import (
    SupplierCreate,
    SupplierListResponse,
    SupplierResponse,
    SupplierUpdate,
)
from app.services.supplier_service import SupplierService

router = APIRouter()


@router.get("", response_model=SupplierListResponse)
async def list_suppliers(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    country: str | None = Query(None),
    category: str | None = Query(None),
    min_rating: float | None = Query(None, ge=0, le=5),
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    service = SupplierService(db)
    return await service.list_suppliers(
        page=page, limit=limit, status=status,
        country=country, category=category, min_rating=min_rating,
    )


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    service = SupplierService(db)
    return await service.get_supplier(supplier_id)


@router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    data: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_admin_or_pm),
):
    service = SupplierService(db)
    return await service.create_supplier(data)


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: str,
    data: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_admin_or_pm),
):
    service = SupplierService(db)
    return await service.update_supplier(supplier_id, data)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    supplier_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_admin),
):
    service = SupplierService(db)
    await service.delete_supplier(supplier_id)
