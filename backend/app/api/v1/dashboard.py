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


@router.get("/quotation-analytics")
async def get_quotation_analytics(
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Aggregated quotation metrics — KPIs, trends, top suppliers."""
    service = DashboardService(db)
    return await service.get_quotation_analytics()


@router.get("/negotiation-analytics")
async def get_negotiation_analytics(
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Aggregated negotiation metrics — success rate, savings, trends."""
    service = DashboardService(db)
    return await service.get_negotiation_analytics()


@router.get("/po-analytics")
async def get_po_analytics(
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Aggregated PO metrics — spend, status, overdue, top suppliers."""
    service = DashboardService(db)
    return await service.get_po_analytics()


@router.get("/supplier-performance")
async def get_supplier_performance(
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Supplier performance — top by value, response times, win rates."""
    service = DashboardService(db)
    return await service.get_supplier_performance()


@router.get("/procurement-overview")
async def get_procurement_overview(
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Cross-cutting procurement analytics for executive overview."""
    service = DashboardService(db)
    return await service.get_procurement_overview()
