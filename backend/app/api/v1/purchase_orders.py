from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_admin_or_pm
from app.database.session import get_db
from app.services.purchase_order_service import PurchaseOrderService

router = APIRouter()


class POCreateRequest(BaseModel):
    rfq_id: str
    quotation_id: str
    delivery_date: str | None = None
    payment_terms: str | None = None
    shipping_address: str | None = None


@router.get("")
async def list_purchase_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all purchase orders for current user."""
    service = PurchaseOrderService(db)
    result = await service.list_purchase_orders(
        user_id=current_user.id, page=page, limit=limit, status=status_filter
    )

    return {
        "items": [
            {
                "id": po.id,
                "po_number": po.po_number,
                "rfq_id": po.rfq_id,
                "supplier_id": po.supplier_id,
                "total_amount": float(po.total_amount),
                "currency": po.currency,
                "delivery_date": str(po.delivery_date) if po.delivery_date else None,
                "status": po.status,
                "pdf_path": po.pdf_path,
                "created_at": po.created_at.isoformat(),
            }
            for po in result["items"]
        ],
        "total": result["total"],
        "page": result["page"],
        "limit": result["limit"],
        "pages": result["pages"],
    }


@router.get("/{po_id}")
async def get_purchase_order(
    po_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get purchase order detail with items."""
    service = PurchaseOrderService(db)
    po = await service.get_purchase_order(po_id)

    return {
        "id": po.id,
        "po_number": po.po_number,
        "rfq_id": po.rfq_id,
        "supplier_id": po.supplier_id,
        "quotation_id": po.quotation_id,
        "total_amount": float(po.total_amount),
        "currency": po.currency,
        "delivery_date": str(po.delivery_date) if po.delivery_date else None,
        "payment_terms": po.payment_terms,
        "shipping_address": po.shipping_address,
        "status": po.status,
        "pdf_path": po.pdf_path,
        "items": [
            {
                "id": item.id,
                "product_name": item.product_name,
                "unit_price": float(item.unit_price),
                "quantity": item.quantity,
                "total_price": float(item.total_price),
            }
            for item in po.items
        ],
        "created_at": po.created_at.isoformat(),
        "updated_at": po.updated_at.isoformat(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    data: POCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a purchase order from an accepted quotation."""
    from datetime import date as date_type

    delivery = None
    if data.delivery_date:
        delivery = date_type.fromisoformat(data.delivery_date)

    service = PurchaseOrderService(db)
    po = await service.create_from_quotation(
        rfq_id=data.rfq_id,
        quotation_id=data.quotation_id,
        user_id=current_user.id,
        delivery_date=delivery,
        payment_terms=data.payment_terms,
        shipping_address=data.shipping_address,
    )

    return {
        "id": po.id,
        "po_number": po.po_number,
        "status": po.status,
        "total_amount": float(po.total_amount),
        "pdf_path": po.pdf_path,
        "message": "Purchase order created successfully",
    }


@router.post("/{po_id}/approve")
async def approve_purchase_order(
    po_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_admin_or_pm),
):
    """Approve a draft purchase order."""
    service = PurchaseOrderService(db)
    po = await service.approve_po(po_id, current_user.id)
    return {"message": f"PO {po.po_number} approved", "status": po.status}


@router.post("/{po_id}/send")
async def send_purchase_order(
    po_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Send purchase order to supplier via email (with PDF attachment)."""
    service = PurchaseOrderService(db)
    result = await service.send_po(po_id, current_user.id)
    return result


@router.get("/{po_id}/pdf")
async def download_po_pdf(
    po_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Download the PO as PDF."""
    import os
    from pathlib import Path
    
    service = PurchaseOrderService(db)
    pdf_path = await service.get_pdf_path(po_id)

    # Ensure the file exists
    if not os.path.exists(pdf_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"PDF file not found at {pdf_path}")

    # Convert to absolute Path to handle both Windows and Unix paths
    pdf_file = Path(pdf_path).resolve()
    filename = pdf_file.name

    return FileResponse(
        path=str(pdf_file),
        media_type="application/pdf",
        filename=filename,
    )
