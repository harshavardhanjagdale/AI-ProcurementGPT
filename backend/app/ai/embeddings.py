"""
Sentence Transformers embedding engine.
Generates vector embeddings for supplier profiles and search queries.
"""
import logging
import pickle

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Lazy-load the embedding model (heavy on first call)."""
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info("Embedding model loaded successfully")
    return _model


def generate_embedding(text: str) -> np.ndarray:
    """Generate embedding vector for a text string."""
    model = get_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding


def generate_embeddings_batch(texts: list[str]) -> list[np.ndarray]:
    """Generate embeddings for multiple texts."""
    model = get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return list(embeddings)


def serialize_embedding(embedding: np.ndarray) -> bytes:
    """Serialize numpy array to bytes for DB storage."""
    return pickle.dumps(embedding)


def deserialize_embedding(data: bytes) -> np.ndarray:
    """Deserialize bytes from DB back to numpy array."""
    return pickle.loads(data)


def build_supplier_profile_text(
    name: str,
    categories: list[str],
    country: str,
    notes: str | None = None,
) -> str:
    """Build a text representation of a supplier for embedding."""
    parts = [
        f"Supplier: {name}",
        f"Categories: {', '.join(categories)}",
        f"Country: {country}",
    ]
    if notes:
        parts.append(f"Notes: {notes}")
    return " | ".join(parts)
