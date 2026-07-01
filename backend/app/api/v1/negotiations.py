from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.services.negotiation_service import NegotiationService

router = APIRouter()


class NegotiationInitRequest(BaseModel):
    rfq_id: str
    supplier_id: str
    quotation_id: str
    target_price: float
    notes: str | None = None


class CounterOfferRequest(BaseModel):
    negotiated_price: float


@router.get("")
async def list_negotiations(
    rfq_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """List negotiations, optionally filtered by RFQ."""
    service = NegotiationService(db)

    if rfq_id:
        negotiations = await service.get_rfq_negotiations(rfq_id)
    else:
        from sqlalchemy import select
        from app.models.negotiation import Negotiation
        result = await db.execute(
            select(Negotiation).order_by(Negotiation.created_at.desc()).limit(50)
        )
        negotiations = list(result.scalars().all())

    return {
        "items": [
            {
                "id": n.id,
                "rfq_id": n.rfq_id,
                "supplier_id": n.supplier_id,
                "quotation_id": n.quotation_id,
                "round_number": n.round_number,
                "original_price": float(n.original_price),
                "target_price": float(n.target_price),
                "negotiated_price": float(n.negotiated_price) if n.negotiated_price else None,
                "status": n.status,
                "created_at": n.created_at.isoformat(),
            }
            for n in negotiations
        ],
        "total": len(negotiations),
    }


@router.get("/{negotiation_id}")
async def get_negotiation(
    negotiation_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get negotiation detail."""
    service = NegotiationService(db)
    n = await service.get_negotiation(negotiation_id)

    return {
        "id": n.id,
        "rfq_id": n.rfq_id,
        "supplier_id": n.supplier_id,
        "quotation_id": n.quotation_id,
        "round_number": n.round_number,
        "original_price": float(n.original_price),
        "target_price": float(n.target_price),
        "negotiated_price": float(n.negotiated_price) if n.negotiated_price else None,
        "status": n.status,
        "ai_strategy_notes": n.ai_strategy_notes,
        "notes": n.notes,
        "created_at": n.created_at.isoformat(),
        "updated_at": n.updated_at.isoformat(),
    }


@router.post("")
async def initiate_negotiation(
    data: NegotiationInitRequest,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Start a new negotiation round with a supplier."""
    service = NegotiationService(db)
    negotiation = await service.initiate_negotiation(
        rfq_id=data.rfq_id,
        supplier_id=data.supplier_id,
        quotation_id=data.quotation_id,
        target_price=data.target_price,
        notes=data.notes,
    )
    return {
        "id": negotiation.id,
        "round_number": negotiation.round_number,
        "status": negotiation.status,
        "message": f"Negotiation round {negotiation.round_number} initiated",
    }


@router.post("/{negotiation_id}/accept")
async def accept_counter_offer(
    negotiation_id: str,
    data: CounterOfferRequest,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Accept a supplier's counter-offer."""
    service = NegotiationService(db)
    negotiation = await service.accept_counter_offer(negotiation_id, data.negotiated_price)
    return {
        "message": "Counter-offer accepted",
        "negotiation_id": negotiation.id,
        "negotiated_price": float(negotiation.negotiated_price),
    }


@router.post("/{negotiation_id}/reject")
async def reject_counter_offer(
    negotiation_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Reject a counter-offer."""
    service = NegotiationService(db)
    negotiation = await service.reject_counter_offer(negotiation_id)
    return {"message": "Counter-offer rejected", "negotiation_id": negotiation.id}
