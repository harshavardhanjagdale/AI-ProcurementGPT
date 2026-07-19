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
from app.ai.llm_client import llm_client

logger = logging.getLogger(__name__)

PO_INTRO_SYSTEM_PROMPT = (
    "You are a professional procurement officer. Write the opening line of a "
    "purchase-order confirmation email to a supplier: warm, concise, and business "
    "appropriate. 1-2 sentences. Do NOT include a greeting (no 'Dear ...'), no "
    "subject, no sign-off, and do not restate the line items or totals — those are "
    "shown in a table below your text. Return ONLY the sentence(s), plain text."
)


async def _draft_po_intro(po, items: list[dict]) -> str | None:
    """
    LLM-draft a short, personalized opening line for the PO email. Best-effort:
    on any failure we return None and the email falls back to the standard
    sentence, so PO delivery is never blocked by the LLM. This call is attributed
    to the workflow run by the token tracker, so the send_po_email node shows real
    token/cost like the other LLM-backed nodes.
    """
    try:
        product_names = ", ".join(i.get("product_name", "") for i in items[:5]) or "the ordered items"
        user_prompt = (
            f"Purchase order {po.po_number} for: {product_names}. "
            f"Total {po.currency} {float(po.total_amount):,.2f}, "
            f"payment terms {po.payment_terms or 'Net 30'}, "
            f"required delivery by {po.delivery_date}. "
            "Write the opening line confirming this order."
        )
        text = await llm_client.generate(
            system_prompt=PO_INTRO_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=200,
        )
        text = (text or "").strip()
        return text or None
    except Exception as e:
        logger.warning(f"PO intro LLM draft failed, using default text: {e}")
        return None


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

            # Which quotation becomes the PO: the one the user explicitly selected
            # (single-select in the UI) wins; otherwise fall back to the AI-recommended
            # quotation, then to the first quotation on the RFQ.
            quotation_id = state.get("selected_quotation_id") or recommendation.get("quotation_id")
            if quotation_id:
                quotation = await quotation_repo.get_with_items(quotation_id)
            else:
                quotation = None
            if quotation is None:
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

            # Tax calculation — prefer quotation tax, fall back to supplier default
            supplier_repo = SupplierRepository(session)
            supplier = await supplier_repo.get_by_id(quotation.supplier_id)

            subtotal = float(quotation.total_amount)
            tax_pct = (
                float(quotation.tax_percent)
                if quotation.tax_percent
                else (float(supplier.default_tax_percent) if supplier and supplier.default_tax_percent else None)
            )
            if tax_pct is None and quotation.currency == "INR":
                tax_pct = 18.0
            tax_amt = round(subtotal * tax_pct / 100, 2) if tax_pct else 0
            grand_total = round(subtotal + tax_amt, 2)

            # Create PO
            po = PurchaseOrder(
                po_number=po_number,
                rfq_id=rfq_id,
                supplier_id=quotation.supplier_id,
                quotation_id=quotation.id,
                user_id=user_id,
                subtotal=subtotal,
                tax_percent=tax_pct,
                tax_amount=tax_amt if tax_pct else None,
                total_amount=grand_total,
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
                subtotal=subtotal,
                tax_percent=tax_pct,
                tax_amount=tax_amt if tax_pct else None,
                total_amount=grand_total,
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
                    "sr_no": idx + 1,
                    "product_name": item.product_name,
                    "quantity": item.quantity,
                    "unit_price": f"{float(item.unit_price):,.2f}",
                    "total_price": f"{float(item.total_price):,.2f}",
                }
                for idx, item in enumerate(quotation.items if quotation else [])
            ]

            # LLM-draft a personalized opening line for the PO email (best-effort).
            intro_message = await _draft_po_intro(po, items_data)

            email_service = EmailService(session)
            result = await email_service.send_purchase_order_email(
                rfq_id=rfq_id,
                supplier_id=po.supplier_id,
                po_number=po.po_number,
                items=items_data,
                subtotal=float(po.subtotal) if po.subtotal else float(po.total_amount),
                tax_percent=float(po.tax_percent) if po.tax_percent else None,
                tax_amount=float(po.tax_amount) if po.tax_amount else None,
                total_amount=float(po.total_amount),
                currency=po.currency,
                payment_terms=po.payment_terms or "Net 30",
                delivery_date=str(po.delivery_date),
                sender_name="Procurement Team",
                pdf_path=po_pdf_path,
                shipping_address=po.shipping_address,
                intro_message=intro_message,
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
