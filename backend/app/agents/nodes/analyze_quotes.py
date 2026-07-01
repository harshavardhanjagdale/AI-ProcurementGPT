"""
Quotation Analysis Node - Uses LLM to score, rank, and recommend suppliers
based on their quotations.
"""
import json
import logging

from app.agents.state import ProcurementState
from app.ai.llm_client import llm_client
from app.database.connection import AsyncSessionLocal
from app.repositories.quotation_repository import QuotationRepository
from app.repositories.supplier_repository import SupplierRepository

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """You are a procurement analysis expert. Analyze and compare supplier quotations to recommend the best option.

Score each quotation on a 0-100 scale considering:
- Price competitiveness (40% weight) - lower is better relative to others
- Delivery speed (25% weight) - fewer days is better
- Warranty coverage (15% weight) - longer/better terms score higher
- Supplier reliability (10% weight) - based on rating
- Payment terms favorability (10% weight) - longer payment terms are better for buyer

Return a JSON object:
{
    "rankings": [
        {
            "quotation_id": "id",
            "supplier_name": "name",
            "score": float (0-100),
            "ranking": integer (1 = best),
            "price_score": float,
            "delivery_score": float,
            "warranty_score": float,
            "reliability_score": float,
            "payment_score": float,
            "strengths": ["list of strengths"],
            "weaknesses": ["list of weaknesses"]
        }
    ],
    "recommendation": {
        "quotation_id": "id of recommended",
        "supplier_name": "name",
        "reasoning": "2-3 sentence explanation of why this is the best choice"
    },
    "summary": "Brief overall comparison summary"
}"""


async def analyze_quotations(state: ProcurementState) -> dict:
    """Analyze and rank all quotations for the RFQ."""
    rfq_id = state.get("rfq_id")

    if not rfq_id:
        return {"current_step": "analyze_quotations", "error": "No RFQ ID"}

    async with AsyncSessionLocal() as session:
        quotation_repo = QuotationRepository(session)
        supplier_repo = SupplierRepository(session)

        quotations = await quotation_repo.get_by_rfq(rfq_id)

        if not quotations:
            return {
                "comparison_matrix": {},
                "ai_recommendation": {},
                "rankings": [],
                "current_step": "analyze_quotations",
                "error": "No quotations found for this RFQ",
            }

        # Build comparison data for LLM
        quotation_summaries = []
        for q in quotations:
            supplier = await supplier_repo.get_by_id(q.supplier_id)
            quotation_summaries.append({
                "quotation_id": q.id,
                "supplier_name": supplier.name if supplier else "Unknown",
                "supplier_rating": float(supplier.rating) if supplier else 0,
                "total_amount": float(q.total_amount),
                "currency": q.currency,
                "delivery_days": q.delivery_days,
                "warranty_terms": q.warranty_terms or "Not specified",
                "payment_terms": q.payment_terms or "Not specified",
                "items_count": len(q.items),
            })

        analysis_prompt = f"""Analyze these {len(quotation_summaries)} quotations and provide scoring and recommendation:

{json.dumps(quotation_summaries, indent=2)}"""

        analysis = await llm_client.generate_json(
            system_prompt=ANALYSIS_SYSTEM_PROMPT,
            user_prompt=analysis_prompt,
            temperature=0.2,
            max_tokens=3000,
        )

        if analysis is None:
            logger.error("LLM analysis returned None")
            return {
                "comparison_matrix": {},
                "ai_recommendation": {},
                "rankings": [],
                "current_step": "analyze_quotations",
                "error": "AI analysis failed",
            }

        # Update DB with scores
        rankings = analysis.get("rankings", [])
        score_updates = []
        for rank_data in rankings:
            score_updates.append({
                "quotation_id": rank_data["quotation_id"],
                "score": rank_data["score"],
                "ranking": rank_data["ranking"],
                "analysis": {
                    "price_score": rank_data.get("price_score"),
                    "delivery_score": rank_data.get("delivery_score"),
                    "warranty_score": rank_data.get("warranty_score"),
                    "reliability_score": rank_data.get("reliability_score"),
                    "strengths": rank_data.get("strengths", []),
                    "weaknesses": rank_data.get("weaknesses", []),
                },
            })

        if score_updates:
            await quotation_repo.update_scores(rfq_id, score_updates)
            await session.commit()

        logger.info(
            f"Analysis complete: {len(rankings)} quotations ranked. "
            f"Recommended: {analysis.get('recommendation', {}).get('supplier_name')}"
        )

        return {
            "comparison_matrix": {"quotations": quotation_summaries},
            "ai_recommendation": analysis.get("recommendation", {}),
            "rankings": rankings,
            "current_step": "analyze_quotations",
        }
