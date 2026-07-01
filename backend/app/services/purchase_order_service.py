"""
Purchase Order Service - Manages PO lifecycle: creation, PDF generation,
approval, and email delivery.
"""
import math
import logging
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.repositories.purchase_order_repository import PurchaseOrderRepository
from app.repositories.quotation_repository import QuotationRepository
from app.repositories.rfq_repository import RFQRepository
from app.repositories.supplier_repository import SupplierRepository
from app.services.email_service import EmailService
from app.utils.pdf_generator import pdf_generator

logger = logging.getLogger(__name__)


class PurchaseOrderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.po_repo = PurchaseOrderRepository(db)
        self.quotation_repo = QuotationRepository(db)
        self.rfq_repo = RFQRepository(db)
        self.supplier_repo = SupplierRepository(db)

    async def create_from_quotation(
        self,
        rfq_id: str,
        quotation_id: str,
        user_id: str,
        delivery_date: date | None = None,
        payment_terms: str | None = None,
        shipping_address: str | None = None,
    ) -> PurchaseOrder:
        """Create a Purchase Order from an accepted quotation."""
        quotation = await self.quotation_repo.get_with_items(quotation_id)
        if not quotation:
            raise NotFoundError("Quotation", quotation_id)

        rfq = await self.rfq_repo.get_by_id(rfq_id)
        if not rfq:
            raise NotFoundError("RFQ", rfq_id)

        # Check if PO already exists for this quotation
        existing_pos = await self.po_repo.get_by_rfq(rfq_id)
        for po in existing_pos:
            if po.quotation_id == quotation_id and po.status != "cancelled":
                raise ValidationError(f"PO already exists for this quotation: {po.po_number}")

        po_number = await self.po_repo.get_next_po_number()

        calc_delivery = delivery_date or (
            date.today() + timedelta(days=quotation.delivery_days or 14)
        )

        po = PurchaseOrder(
            po_number=po_number,
            rfq_id=rfq_id,
            supplier_id=quotation.supplier_id,
            quotation_id=quotation_id,
            user_id=user_id,
            total_amount=quotation.total_amount,
            currency=quotation.currency,
            delivery_date=calc_delivery,
            payment_terms=payment_terms or quotation.payment_terms or "Net 30",
            shipping_address=shipping_address,
            status="draft",
        )
        po = await self.po_repo.create(po)

        for q_item in quotation.items:
            po_item = PurchaseOrderItem(
                po_id=po.id,
                product_name=q_item.product_name,
                unit_price=q_item.unit_price,
                quantity=q_item.quantity,
                total_price=q_item.total_price,
            )
            self.db.add(po_item)

        # Mark quotation as accepted
        await self.quotation_repo.update_by_id(quotation_id, {"status": "accepted"})

        # Update RFQ status
        await self.rfq_repo.update_by_id(rfq_id, {"status": "po_generated"})

        await self.db.flush()

        # Generate PDF
        await self._generate_pdf(po.id)

        logger.info(f"Created PO {po_number} from quotation {quotation_id}")
        return await self.po_repo.get_with_items(po.id)

    async def _generate_pdf(self, po_id: str) -> str:
        """Generate PDF for a purchase order."""
        po = await self.po_repo.get_with_items(po_id)
        if not po:
            raise NotFoundError("PurchaseOrder", po_id)

        supplier = await self.supplier_repo.get_by_id(po.supplier_id)
        rfq = await self.rfq_repo.get_by_id(po.rfq_id)

        items_data = [
            {
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "total_price": float(item.total_price),
            }
            for item in po.items
        ]

        pdf_path = pdf_generator.generate(
            po_number=po.po_number,
            rfq_number=rfq.rfq_number if rfq else "N/A",
            supplier_name=supplier.name if supplier else "Unknown",
            supplier_email=supplier.email if supplier else "",
            supplier_address=supplier.address if supplier else None,
            items=items_data,
            total_amount=float(po.total_amount),
            currency=po.currency,
            delivery_date=str(po.delivery_date) if po.delivery_date else "TBD",
            payment_terms=po.payment_terms or "Net 30",
            shipping_address=po.shipping_address,
        )

        await self.po_repo.update_by_id(po_id, {"pdf_path": pdf_path})
        return pdf_path

    async def get_purchase_order(self, po_id: str) -> PurchaseOrder:
        po = await self.po_repo.get_with_items(po_id)
        if not po:
            raise NotFoundError("PurchaseOrder", po_id)
        return po

    async def list_purchase_orders(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        status: str | None = None,
    ) -> dict:
        skip = (page - 1) * limit
        pos = await self.po_repo.get_user_pos(user_id, status=status, skip=skip, limit=limit)
        total = await self.po_repo.count_user_pos(user_id, status=status)

        return {
            "items": pos,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": math.ceil(total / limit) if total > 0 else 0,
        }

    async def approve_po(self, po_id: str, user_id: str) -> PurchaseOrder:
        """Approve a draft PO."""
        po = await self.po_repo.get_by_id(po_id)
        if not po:
            raise NotFoundError("PurchaseOrder", po_id)
        if po.status != "draft":
            raise ValidationError(f"Cannot approve PO in '{po.status}' status")

        await self.po_repo.update_by_id(po_id, {"status": "approved"})
        return await self.po_repo.get_with_items(po_id)

    async def send_po(self, po_id: str, user_id: str) -> dict:
        """Send approved PO to supplier via email."""
        po = await self.po_repo.get_with_items(po_id)
        if not po:
            raise NotFoundError("PurchaseOrder", po_id)
        if po.status not in ("draft", "approved"):
            raise ValidationError(f"Cannot send PO in '{po.status}' status")

        # Ensure PDF exists
        if not po.pdf_path:
            await self._generate_pdf(po_id)
            po = await self.po_repo.get_with_items(po_id)

        rfq = await self.rfq_repo.get_by_id(po.rfq_id)
        quotation = await self.quotation_repo.get_with_items(po.quotation_id)

        items_data = [
            {
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price": f"{float(item.unit_price):,.2f}",
                "total_price": f"{float(item.total_price):,.2f}",
            }
            for item in po.items
        ]

        email_service = EmailService(self.db)
        result = await email_service.send_purchase_order_email(
            rfq_id=po.rfq_id,
            supplier_id=po.supplier_id,
            po_number=po.po_number,
            items=items_data,
            total_amount=float(po.total_amount),
            currency=po.currency,
            payment_terms=po.payment_terms or "Net 30",
            delivery_date=str(po.delivery_date),
            sender_name="Procurement Team",
            pdf_path=po.pdf_path,
            shipping_address=po.shipping_address,
        )

        if result["success"]:
            await self.po_repo.update_by_id(po_id, {
                "status": "sent",
                "email_id": result.get("email_id"),
            })

        # Update RFQ to completed
        await self.rfq_repo.update_by_id(po.rfq_id, {"status": "completed"})

        return {
            "success": result["success"],
            "po_number": po.po_number,
            "email_id": result.get("email_id"),
            "error": result.get("error"),
        }

    async def get_pdf_path(self, po_id: str) -> str:
        """Get PDF file path for download."""
        po = await self.po_repo.get_by_id(po_id)
        if not po:
            raise NotFoundError("PurchaseOrder", po_id)
        if not po.pdf_path:
            return await self._generate_pdf(po_id)
        return po.pdf_path
