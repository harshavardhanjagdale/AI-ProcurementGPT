"""
Vendor Selection Node - Uses embedding similarity + DB filters
to find the top suppliers for an RFQ.
"""
import logging

from app.agents.state import ProcurementState
from app.ai.vector_search import rank_suppliers_by_similarity
from app.database.connection import AsyncSessionLocal
from app.repositories.supplier_repository import SupplierRepository

logger = logging.getLogger(__name__)


async def select_vendors(state: ProcurementState) -> dict:
    """Select top suppliers based on RFQ requirements using embedding search."""
    parsed = state["parsed_intent"]
    categories = parsed.get("categories", [])
    title = parsed.get("title", "")
    description = parsed.get("description", "")

    query_text = f"{title}. {description}. Categories: {', '.join(categories)}"

    logger.info(f"Selecting vendors for: {query_text[:100]}...")

    async with AsyncSessionLocal() as session:
        repo = SupplierRepository(session)

        if categories:
            suppliers = await repo.get_active_by_categories(categories, limit=20)
        else:
            suppliers = await repo.search(status="active", limit=20)

        if not suppliers:
            return {
                "selected_suppliers": [],
                "supplier_scores": [],
                "current_step": "select_vendors",
                "error": "No active suppliers found matching criteria",
            }

        supplier_data = [
            {
                "id": s.id,
                "name": s.name,
                "email": s.email,
                "country": s.country,
                "rating": float(s.rating),
                "avg_delivery_days": s.avg_delivery_days,
                "categories": [c.category_name for c in s.categories],
                "embedding_vector": s.embedding_vector,
                "notes": s.notes,
            }
            for s in suppliers
        ]

    ranked = rank_suppliers_by_similarity(
        query_text=query_text,
        suppliers=supplier_data,
        top_k=5,
    )

    selected = []
    scores = []
    for r in ranked:
        selected.append({
            "id": r["id"],
            "name": r["name"],
            "email": r["email"],
            "country": r["country"],
            "rating": r["rating"],
            "avg_delivery_days": r["avg_delivery_days"],
            "categories": r["categories"],
        })
        scores.append({
            "supplier_id": r["id"],
            "supplier_name": r["name"],
            "relevance_score": r["relevance_score"],
            "rating": r["rating"],
        })

    # Link selected suppliers to the RFQ in DB
    rfq_id = state.get("rfq_id")
    if rfq_id and selected:
        from app.models.rfq_supplier import RFQSupplier
        from app.models.base import generate_uuid
        async with AsyncSessionLocal() as session:
            for s in selected:
                rfq_supplier = RFQSupplier(
                    id=generate_uuid(),
                    rfq_id=rfq_id,
                    supplier_id=s["id"],
                    status="selected",
                )
                session.add(rfq_supplier)
            from sqlalchemy import update
            from app.models.rfq import RFQ
            await session.execute(
                update(RFQ).where(RFQ.id == rfq_id).values(status="vendors_selected")
            )
            await session.commit()

    logger.info(f"Selected {len(selected)} vendors: {[s['name'] for s in selected]}")

    return {
        "selected_suppliers": selected,
        "supplier_scores": scores,
        "current_step": "select_vendors",
    }
