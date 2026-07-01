from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.schemas.rfq import (
    RFQCreate,
    RFQListResponse,
    RFQResponse,
    RFQUpdate,
)
from app.services.rfq_service import RFQService

router = APIRouter()


@router.get("", response_model=RFQListResponse)
async def list_rfqs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = RFQService(db)
    return await service.list_rfqs(
        user_id=current_user.id, page=page, limit=limit, status=status_filter
    )


@router.get("/{rfq_id}", response_model=RFQResponse)
async def get_rfq(
    rfq_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    service = RFQService(db)
    return await service.get_rfq(rfq_id)


@router.post("", response_model=RFQResponse, status_code=status.HTTP_201_CREATED)
async def create_rfq(
    data: RFQCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = RFQService(db)
    return await service.create_rfq(user_id=current_user.id, data=data)


@router.put("/{rfq_id}", response_model=RFQResponse)
async def update_rfq(
    rfq_id: str,
    data: RFQUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = RFQService(db)
    return await service.update_rfq(rfq_id=rfq_id, user_id=current_user.id, data=data)


@router.delete("/{rfq_id}", response_model=RFQResponse)
async def cancel_rfq(
    rfq_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = RFQService(db)
    return await service.cancel_rfq(rfq_id=rfq_id, user_id=current_user.id)
