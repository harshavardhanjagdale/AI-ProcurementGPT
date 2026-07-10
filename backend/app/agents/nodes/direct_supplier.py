"""
Direct Supplier Node - When the user explicitly names one or more suppliers,
find them in the DB and set them as the selected vendors.

A procurement manager types supplier names the way they remember them —
"tech supply", "alpha components", "globaltech" — not the exact registered name
("TechSupply Corp", "Alpha Components", "GlobalTech Solutions"). A naive
`name ILIKE %tech supply%` never matches "TechSupply Corp" (the space breaks it),
and the old code only ever used the first match even when several suppliers were
named. This resolver fixes both: it splits multiple named suppliers and matches
each with a spacing/suffix-tolerant fuzzy matcher.
"""
import logging
import re

from sqlalchemy import select

from app.agents.state import ProcurementState
from app.database.connection import AsyncSessionLocal
from app.models.supplier import Supplier

logger = logging.getLogger(__name__)

# Legal-entity suffixes and filler words that shouldn't drive a match — a user
# almost never types these, so we ignore them when comparing names.
_NOISE_WORDS = {
    "corp", "corporation", "inc", "incorporated", "ltd", "limited", "llc", "llp",
    "plc", "gmbh", "co", "company", "pvt", "private", "group", "holdings",
    "international", "intl", "the", "and",
}

# Minimum confidence to accept a fuzzy match (0..1). Below this we treat the
# named supplier as "not found" rather than guess wrongly.
_MATCH_THRESHOLD = 0.6


def _normalize(s: str) -> str:
    """Lowercase, strip punctuation to spaces, collapse whitespace."""
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _spaceless(s: str) -> str:
    return _normalize(s).replace(" ", "")


def _core_tokens(s: str) -> set[str]:
    return {t for t in _normalize(s).split() if t not in _NOISE_WORDS}


def _match_score(query: str, name: str) -> float:
    """
    How well a user-typed name matches a registered supplier name (0..1).
    Tolerant to spacing ("tech supply" ~ "TechSupply"), legal suffixes
    ("TechSupply Corp"), case, and punctuation.
    """
    q_core = _core_tokens(query)
    if not q_core:
        return 0.0

    q_sl, n_sl = _spaceless(query), _spaceless(name)
    n_core = _core_tokens(name)

    # Spaceless containment: "techsupply" in "techsupplycorp" -> strong match.
    if q_sl and q_sl in n_sl:
        return 1.0
    if n_sl and n_sl in q_sl:
        return 0.95

    # All of the user's words appear somewhere in the supplier's spaceless name
    # ("alpha components" -> "alphacomponents"): strong match.
    token_hits = sum(1 for t in q_core if t in n_sl)
    token_frac = token_hits / len(q_core)
    if q_core.issubset(n_core):
        return max(0.9, token_frac)

    # Otherwise fall back to token overlap (Jaccard) vs. the substring fraction.
    if n_core:
        jaccard = len(q_core & n_core) / len(q_core | n_core)
    else:
        jaccard = 0.0
    return max(token_frac, jaccard)


def _split_supplier_names(raw: str) -> list[str]:
    """Split a possibly-multi-supplier string into individual names.

    Handles "Alpha Components and TechSupply", "A, B & C", "A / B", etc.
    """
    raw = re.sub(r"^\s*from\s+", "", raw or "", flags=re.IGNORECASE)
    parts = re.split(r"\s*(?:,|/|\+|&|\band\b)\s*", raw, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p and p.strip()]


def _best_match(query: str, suppliers: list[Supplier]) -> tuple[Supplier | None, float]:
    best, best_score = None, 0.0
    for sup in suppliers:
        score = _match_score(query, sup.name)
        # Tie-break toward the more specific (shorter) registered name.
        if score > best_score or (score == best_score and best and len(sup.name) < len(best.name)):
            best, best_score = sup, score
    return best, best_score


async def resolve_direct_supplier(state: ProcurementState) -> dict:
    """Find the named supplier(s) in the database by fuzzy name match."""
    parsed = state["parsed_intent"]
    raw = parsed.get("direct_supplier", "") or ""
    names = _split_supplier_names(raw)

    if not names:
        return {
            "selected_suppliers": [],
            "current_step": "resolve_direct_supplier",
            "error": "No direct supplier specified",
        }

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Supplier).where(Supplier.status == "active")
        )
        all_suppliers = list(result.scalars().all())

    selected: list[dict] = []
    scores: list[dict] = []
    matched_ids: set[str] = set()
    unmatched: list[str] = []

    for name in names:
        supplier, score = _best_match(name, all_suppliers)
        if supplier is None or score < _MATCH_THRESHOLD:
            unmatched.append(name)
            logger.warning(f"Direct supplier '{name}' not matched (best score {score:.2f})")
            continue
        if supplier.id in matched_ids:
            continue
        matched_ids.add(supplier.id)
        logger.info(f"Direct supplier '{name}' -> '{supplier.name}' (score {score:.2f})")
        selected.append({
            "id": supplier.id,
            "name": supplier.name,
            "email": supplier.email,
            "country": supplier.country,
            "rating": float(supplier.rating) if supplier.rating else 0,
            "avg_delivery_days": supplier.avg_delivery_days,
            "categories": [],
        })
        scores.append({
            "supplier_id": supplier.id,
            "supplier_name": supplier.name,
            "relevance_score": round(score, 4),
            "rating": float(supplier.rating) if supplier.rating else 0,
        })

    if not selected:
        return {
            "selected_suppliers": [],
            "supplier_scores": [],
            "current_step": "resolve_direct_supplier",
            "error": (
                f"Could not find any supplier matching: {', '.join(names)}. "
                "Will search for alternatives."
            ),
        }

    if unmatched:
        logger.info(f"Matched {len(selected)} supplier(s); could not match: {unmatched}")

    return {
        "selected_suppliers": selected,
        "supplier_scores": scores,
        "current_step": "resolve_direct_supplier",
    }


def route_after_direct_supplier(state: ProcurementState) -> str:
    """Stop the workflow if none of the named suppliers were found."""
    if not state.get("selected_suppliers"):
        return "no_supplier"
    return "create_rfq_record"
