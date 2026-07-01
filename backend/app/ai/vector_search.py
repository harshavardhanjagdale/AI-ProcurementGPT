"""
Vector similarity search for supplier matching.
Uses cosine similarity between query embedding and stored supplier embeddings.
"""
import logging

import numpy as np

from app.ai.embeddings import (
    deserialize_embedding,
    generate_embedding,
    serialize_embedding,
    build_supplier_profile_text,
)

logger = logging.getLogger(__name__)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def rank_suppliers_by_similarity(
    query_text: str,
    suppliers: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """
    Rank suppliers by semantic similarity to a query.

    Args:
        query_text: The RFQ description or search query
        suppliers: List of dicts with 'id', 'name', 'embedding_vector' (bytes), etc.
        top_k: Number of top results to return

    Returns:
        Sorted list of suppliers with relevance scores
    """
    query_embedding = generate_embedding(query_text)

    scored_suppliers = []
    for supplier in suppliers:
        embedding_bytes = supplier.get("embedding_vector")
        if embedding_bytes is None:
            # Generate embedding on-the-fly if not stored
            profile_text = build_supplier_profile_text(
                name=supplier["name"],
                categories=supplier.get("categories", []),
                country=supplier.get("country", ""),
                notes=supplier.get("notes"),
            )
            supplier_embedding = generate_embedding(profile_text)
        else:
            supplier_embedding = deserialize_embedding(embedding_bytes)

        score = cosine_similarity(query_embedding, supplier_embedding)
        scored_suppliers.append({
            **supplier,
            "relevance_score": round(score, 4),
        })

    scored_suppliers.sort(key=lambda x: x["relevance_score"], reverse=True)

    return scored_suppliers[:top_k]


def generate_supplier_embedding_data(
    name: str,
    categories: list[str],
    country: str,
    notes: str | None = None,
) -> bytes:
    """Generate and serialize an embedding for a supplier profile."""
    profile_text = build_supplier_profile_text(name, categories, country, notes)
    embedding = generate_embedding(profile_text)
    return serialize_embedding(embedding)
