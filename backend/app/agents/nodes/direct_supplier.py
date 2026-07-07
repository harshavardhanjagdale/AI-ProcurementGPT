"""
Direct Supplier Node - When user explicitly names a supplier,
find that supplier in DB and set them as the only selected vendor.
"""
import logging

from sqlalchemy import select

from app.agents.state import ProcurementState
from app.database.connection import AsyncSessionLocal
from app.models.supplier import Supplier

logger = logging.getLogger(__name__)


async def resolve_direct_supplier(state: ProcurementState) -> dict:
    """Find the named supplier in the database by fuzzy name match."""
    parsed = state["parsed_intent"]
    supplier_name = parsed.get("direct_supplier", "")

    if not supplier_name:
        return {
            "selected_suppliers": [],
            "current_step": "resolve_direct_supplier",
            "error": "No direct supplier specified",
        }

    async with AsyncSessionLocal() as session:
        # Try exact match first, then LIKE match
        result = await session.execute(
            select(Supplier).where(
                Supplier.status == "active",
                Supplier.name.ilike(f"%{supplier_name}%"),
            )
        )
        suppliers = list(result.scalars().all())

        if not suppliers:
            logger.warning(f"Direct supplier '{supplier_name}' not found, falling back to search")
            return {
                "selected_suppliers": [],
                "supplier_scores": [],
                "current_step": "resolve_direct_supplier",
                "error": f"Supplier '{supplier_name}' not found in database. Will search for alternatives.",
            }

        supplier = suppliers[0]
        selected = [{
            "id": supplier.id,
            "name": supplier.name,
            "email": supplier.email,
            "country": supplier.country,
            "rating": float(supplier.rating) if supplier.rating else 0,
            "avg_delivery_days": supplier.avg_delivery_days,
            "categories": [],
        }]

        logger.info(f"Direct supplier resolved: {supplier.name} ({supplier.email})")

        return {
            "selected_suppliers": selected,
            "supplier_scores": [{
                "supplier_id": supplier.id,
                "supplier_name": supplier.name,
                "relevance_score": 1.0,
                "rating": float(supplier.rating) if supplier.rating else 0,
            }],
            "current_step": "resolve_direct_supplier",
        }


def route_after_direct_supplier(state: ProcurementState) -> str:
    """Stop the workflow if the named supplier was not found."""
    if not state.get("selected_suppliers"):
        return "no_supplier"
    return "create_rfq_record"
