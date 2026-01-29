"""Shared embedding model singleton – loads once on first use."""

from loguru import logger
from sentence_transformers import SentenceTransformer

from app.core.config import settings

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Return the shared SentenceTransformer, loading it on first call.

    This avoids loading the model twice (once for ingestion, once for search)
    and defers loading until actually needed, so the app starts quickly.
    """
    global _model
    if _model is None:
        logger.info(f"Loading embedding model (first use): {settings.EMBEDDING_MODEL_NAME}...")
        _model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        logger.info("Embedding model loaded.")
    return _model
