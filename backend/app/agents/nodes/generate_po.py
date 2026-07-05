"""
Purchase Order Generation Node - Creates PO record, generates PDF, and sends email.
"""
import asyncio
import logging
from datetime import date, timedelta

from app.agents.state import ProcurementState
from app.database.connection import AsyncSessionLocal
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.repositories.quotation_repository import QuotationRepository
from app.repositories.rfq_repository import RFQRepository
from app.repositories.supplier_repository import SupplierRepository
from app.services.email_service import EmailService
from app.utils.pdf_generator import pdf_generator

logger = logging.getLogger(__name__)


async def generate_purchase_order(state: ProcurementState) -> dict:
    """Generate a purchase order from the accepted/recommended quotation."""
    rfq_id = state.get("rfq_id")
    user_id = state.get("user_id")
    recommendation = state.get("ai_recommendation", {})

    if not rfq_id:
        return {
            "po_generated": False,
            "current_step": "generate_purchase_order",
            "error": "No RFQ ID",
        }

    async with AsyncSessionLocal() as session:
        try:
            rfq_repo = RFQRepository(session)
            quotation_repo = QuotationRepository(session)

            rfq = await rfq_repo.get_by_id(rfq_id)
            if not rfq:
                return {"po_generated": False, "error": "RFQ not found"}

            # Find the accepted/recommended quotation
            quotation_id = recommendation.get("quotation_id")
            if quotation_id:
                quotation = await quotation_repo.get_with_items(quotation_id)
            else:
                quotations = await quotation_repo.get_by_rfq(rfq_id)
                quotation = quotations[0] if quotations else None

            if not quotation:
                return {"po_generated": False, "error": "No quotation found"}

            # Generate PO number
            from sqlalchemy import select, func
            result = await session.execute(
                select(func.count(PurchaseOrder.id))
            )
            po_count = result.scalar_one()
            from datetime import datetime, timezone
            year = datetime.now(timezone.utc).year
            po_number = f"PO-{year}-{(po_count + 1):05d}"

            # Calculate delivery date
            delivery_days = quotation.delivery_days or 14
            delivery_date = date.today() + timedelta(days=delivery_days)

            # Create PO
            po = PurchaseOrder(
                po_number=po_number,
                rfq_id=rfq_id,
                supplier_id=quotation.supplier_id,
                quotation_id=quotation.id,
                user_id=user_id,
                total_amount=quotation.total_amount,
                currency=quotation.currency,
                delivery_date=delivery_date,
                payment_terms=quotation.payment_terms or "Net 30",
                status="draft",
            )
            session.add(po)
            await session.flush()

            # Add PO items from quotation items
            for q_item in quotation.items:
                po_item = PurchaseOrderItem(
                    po_id=po.id,
                    product_name=q_item.product_name,
                    unit_price=q_item.unit_price,
                    quantity=q_item.quantity,
                    total_price=q_item.total_price,
                )
                session.add(po_item)

            # Update RFQ status
            await rfq_repo.update_by_id(rfq_id, {"status": "po_generated"})

            # Update quotation status
            await quotation_repo.update_by_id(quotation.id, {"status": "accepted"})

            await session.commit()

            logger.info(f"Generated PO {po_number} for RFQ {rfq.rfq_number}")

            # Generate the PDF document for this PO
            supplier_repo = SupplierRepository(session)
            supplier = await supplier_repo.get_by_id(quotation.supplier_id)

            pdf_items = [
                {
                    "product_name": item.product_name,
                    "quantity": item.quantity,
                    "unit_price": float(item.unit_price),
                    "total_price": float(item.total_price),
                }
                for item in quotation.items
            ]

            pdf_path = await asyncio.to_thread(
                pdf_generator.generate,
                po_number=po_number,
                rfq_number=rfq.rfq_number,
                supplier_name=supplier.name if supplier else "Unknown Supplier",
                supplier_email=supplier.email if supplier else "",
                supplier_address=supplier.address if supplier else None,
                items=pdf_items,
                total_amount=float(quotation.total_amount),
                currency=quotation.currency,
                delivery_date=str(delivery_date),
                payment_terms=quotation.payment_terms or "Net 30",
                shipping_address=po.shipping_address,
            )

            from sqlalchemy import update
            await session.execute(
                update(PurchaseOrder).where(PurchaseOrder.id == po.id).values(pdf_path=pdf_path)
            )
            await session.commit()

            logger.info(f"Generated PO PDF at {pdf_path}")

            return {
                "po_generated": True,
                "po_pdf_path": pdf_path,
                "current_step": "generate_purchase_order",
            }
        except Exception as e:
            await session.rollback()
            logger.error(f"PO generation failed: {e}")
            return {
                "po_generated": False,
                "current_step": "generate_purchase_order",
                "error": str(e),
            }


async def send_po_email(state: ProcurementState) -> dict:
    """Send the purchase order email to the supplier."""
    rfq_id = state.get("rfq_id")
    po_pdf_path = state.get("po_pdf_path")

    if not rfq_id:
        return {"po_email_sent": False, "error": "No RFQ ID"}

    async with AsyncSessionLocal() as session:
        try:
            from sqlalchemy import select
            result = await session.execute(
                select(PurchaseOrder).where(PurchaseOrder.rfq_id == rfq_id).order_by(PurchaseOrder.created_at.desc())
            )
            po = result.scalar_one_or_none()

            if not po:
                return {"po_email_sent": False, "error": "No PO found"}

            from app.repositories.quotation_repository import QuotationRepository
            quotation_repo = QuotationRepository(session)
            quotation = await quotation_repo.get_with_items(po.quotation_id)

            items_data = [
                {
                    "product_name": item.product_name,
                    "quantity": item.quantity,
                    "unit_price": f"{float(item.unit_price):,.2f}",
                    "total_price": f"{float(item.total_price):,.2f}",
                }
                for item in (quotation.items if quotation else [])
            ]

            email_service = EmailService(session)
            result = await email_service.send_purchase_order_email(
                rfq_id=rfq_id,
                supplier_id=po.supplier_id,
                po_number=po.po_number,
                items=items_data,
                total_amount=float(po.total_amount),
                currency=po.currency,
                payment_terms=po.payment_terms or "Net 30",
                delivery_date=str(po.delivery_date),
                sender_name="Procurement Team",
                pdf_path=po_pdf_path,
                shipping_address=po.shipping_address,
            )

            # Update PO status to sent
            from sqlalchemy import update
            await session.execute(
                update(PurchaseOrder).where(PurchaseOrder.id == po.id).values(status="sent")
            )
            await session.commit()

            logger.info(f"PO email sent for {po.po_number}")

            return {
                "po_email_sent": result["success"],
                "current_step": "send_po_email",
            }
        except Exception as e:
            await session.rollback()
            logger.error(f"PO email failed: {e}")
            return {"po_email_sent": False, "error": str(e)}
