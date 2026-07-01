from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get overview dashboard statistics."""
    service = DashboardService(db)
    return await service.get_stats()


@router.get("/recent-activity")
async def get_recent_activity(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get recent system activity."""
    service = DashboardService(db)
    activities = await service.get_recent_activity(limit)
    return {"activities": activities}


@router.get("/rfq-pipeline")
async def get_rfq_pipeline(
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get RFQ pipeline distribution by status."""
    service = DashboardService(db)
    pipeline = await service.get_rfq_pipeline()
    return {"pipeline": pipeline}
