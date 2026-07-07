from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.services.quotation_service import QuotationService
from app.services.ocr_service import OCRService

router = APIRouter()


@router.get("")
async def list_quotations(
    rfq_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """List quotations, optionally filtered by RFQ."""
    service = QuotationService(db)

    if rfq_id:
        quotations = await service.get_rfq_quotations(rfq_id)
    else:
        from sqlalchemy import select
        from app.models.quotation import Quotation
        result = await db.execute(
            select(Quotation).order_by(Quotation.created_at.desc()).limit(50)
        )
        quotations = list(result.scalars().all())

    return {
        "items": [
            {
                "id": q.id,
                "rfq_id": q.rfq_id,
                "supplier_id": q.supplier_id,
                "total_amount": float(q.total_amount),
                "currency": q.currency,
                "delivery_days": q.delivery_days,
                "warranty_terms": q.warranty_terms,
                "ai_score": float(q.ai_score) if q.ai_score else None,
                "ai_ranking": q.ai_ranking,
                "status": q.status,
                "created_at": q.created_at.isoformat(),
            }
            for q in quotations
        ],
        "total": len(quotations),
    }


@router.get("/{quotation_id}")
async def get_quotation(
    quotation_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get detailed quotation with line items."""
    service = QuotationService(db)
    quotation = await service.get_quotation(quotation_id)

    return {
        "id": quotation.id,
        "rfq_id": quotation.rfq_id,
        "supplier_id": quotation.supplier_id,
        "total_amount": float(quotation.total_amount),
        "currency": quotation.currency,
        "delivery_days": quotation.delivery_days,
        "warranty_terms": quotation.warranty_terms,
        "payment_terms": quotation.payment_terms,
        "validity_days": quotation.validity_days,
        "ai_score": float(quotation.ai_score) if quotation.ai_score else None,
        "ai_ranking": quotation.ai_ranking,
        "ai_analysis": quotation.ai_analysis_json,
        "status": quotation.status,
        "raw_ocr_text": quotation.raw_ocr_text,
        "items": [
            {
                "id": item.id,
                "product_name": item.product_name,
                "unit_price": float(item.unit_price),
                "quantity": item.quantity,
                "total_price": float(item.total_price),
                "specifications": item.specifications,
            }
            for item in quotation.items
        ],
        "created_at": quotation.created_at.isoformat(),
        "updated_at": quotation.updated_at.isoformat(),
    }


@router.get("/rfq/{rfq_id}")
async def list_quotations_by_rfq(
    rfq_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """List all quotations for a specific RFQ with supplier details."""
    service = QuotationService(db)
    quotations = await service.get_rfq_quotations(rfq_id)

    return [
        {
            "id": q.id,
            "rfq_id": q.rfq_id,
            "supplier_id": q.supplier_id,
            "supplier_name": q.supplier.name if q.supplier else "Unknown",
            "total_amount": float(q.total_amount),
            "tax_percent": float(q.tax_percent) if q.tax_percent else None,
            "tax_amount": float(q.tax_amount) if q.tax_amount else None,
            "grand_total": float(q.grand_total) if q.grand_total else None,
            "currency": q.currency,
            "delivery_days": q.delivery_days,
            "warranty_terms": q.warranty_terms,
            "payment_terms": q.payment_terms,
            "validity_days": q.validity_days,
            "ai_score": float(q.ai_score) if q.ai_score else None,
            "ai_ranking": q.ai_ranking,
            "status": q.status,
            "negotiation_round": q.negotiation_round or 0,
            "items": [
                {
                    "id": item.id,
                    "product_name": item.product_name,
                    "unit_price": float(item.unit_price),
                    "quantity": item.quantity,
                    "total_price": float(item.total_price),
                    "specifications": item.specifications,
                }
                for item in q.items
            ],
            "created_at": q.created_at.isoformat() if q.created_at else None,
        }
        for q in quotations
    ]


@router.get("/rfq/{rfq_id}/compare")
async def compare_quotations(
    rfq_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get side-by-side comparison of all quotations for an RFQ."""
    service = QuotationService(db)
    return await service.get_comparison(rfq_id)


@router.post("/{quotation_id}/accept")
async def accept_quotation(
    quotation_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Accept a quotation (rejects all others for same RFQ)."""
    service = QuotationService(db)
    quotation = await service.accept_quotation(quotation_id)
    return {"message": "Quotation accepted", "quotation_id": quotation.id}


@router.post("/{quotation_id}/reject")
async def reject_quotation(
    quotation_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Reject a quotation."""
    service = QuotationService(db)
    quotation = await service.reject_quotation(quotation_id)
    return {"message": "Quotation rejected", "quotation_id": quotation.id}


@router.post("/rfq/{rfq_id}/process-ocr")
async def process_rfq_ocr(
    rfq_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Trigger OCR processing for all unprocessed attachments of an RFQ."""
    service = OCRService(db)
    result = await service.process_rfq_attachments(rfq_id)
    return result


@router.post("/attachment/{attachment_id}/process")
async def process_single_attachment(
    attachment_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Process a specific email attachment through OCR."""
    service = QuotationService(db)
    result = await service.process_attachment(attachment_id)
    return result
