"""Embedding generation and Pinecone upsert for RAG ingestion."""

import json
from typing import Any, Dict, List

from loguru import logger
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

from app.core.config import settings


class VectorService:
    """Generate embeddings and upsert chunks to Pinecone.

    Uses SentenceTransformer (e.g. BGE-Small) for embeddings. Chunks are
    sent in batches of 100 for efficient upserts.
    """

    def __init__(self) -> None:
        """Load the embedding model and connect to Pinecone."""
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL_NAME}...")
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        
        # Initializing Pinecone
        self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index = self.pc.Index(settings.PINECONE_INDEX_NAME)
        logger.info("Pinecone connection established.")

    @staticmethod
    def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize metadata to only include Pinecone-compatible types.
        
        Pinecone accepts: string, number, boolean, or list of strings.
        Complex objects (dicts, lists of non-strings) are either:
        - Converted to JSON strings (for important fields)
        - Removed (for non-essential fields like coordinates)
        
        Args:
            metadata: Raw metadata dictionary from document processing.
            
        Returns:
            Sanitized metadata dictionary compatible with Pinecone.
        """
        sanitized = {}
        
        # Fields to exclude (complex objects that aren't useful for search)
        exclude_fields = {'coordinates', 'parent_id', 'element_id', 'orig_elements'}
        
        # Fields to convert to JSON strings (important but complex)
        json_fields = {'metadata_json'}  # Can add more if needed
        
        for key, value in metadata.items():
            # Skip excluded fields
            if key in exclude_fields:
                continue
            
            # Skip None values
            if value is None:
                continue
            
            # Handle different types
            if isinstance(value, (str, int, float, bool)):
                # Primitive types are fine
                sanitized[key] = value
            elif isinstance(value, list):
                # Check if it's a list of strings
                if all(isinstance(item, str) for item in value):
                    sanitized[key] = value
                elif key in json_fields:
                    # Convert complex lists to JSON string
                    sanitized[key] = json.dumps(value)
                # Otherwise skip non-string lists
            elif isinstance(value, dict):
                # Convert dicts to JSON strings for important fields
                if key in json_fields:
                    sanitized[key] = json.dumps(value)
                # Otherwise skip dicts (like coordinates)
            else:
                # Try to convert to string for unknown types
                try:
                    sanitized[key] = str(value)
                except Exception:
                    # Skip if conversion fails
                    logger.debug(f"Skipping metadata field '{key}' with unsupported type: {type(value)}")
        
        return sanitized

    async def upsert_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """Embed text chunks and upsert them to Pinecone in batches of 100.

        Each chunk must have "id", "text", and "metadata". Metadata should
        include user_id, filename, and "text" for retrieval. Logs progress
        and re-raises on upsert errors.

        Args:
            chunks: List of dicts with id, text, metadata.

        Raises:
            Exception: Propagates any Pinecone or encoding error.
        """
        if not chunks:
            logger.warning("No chunks provided for upsert.")
            return

        # Grouping chunks to reduce network overhead. Pinecone handles batches of 100 well.
        batch_size = 100
        total_chunks = len(chunks)
        
        logger.info(f"Starting upsert for {total_chunks} chunks...")

        for i in range(0, total_chunks, batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c["text"] for c in batch]
            
            try:
                # Generating Embeddings
                embeddings = self.model.encode(texts, convert_to_numpy=True).tolist()
                
                # Preparing Pinecone Records
                vectors_to_upsert = []
                for chunk, emb in zip(batch, embeddings):
                    # Sanitize metadata to ensure Pinecone compatibility
                    sanitized_metadata = self._sanitize_metadata(chunk["metadata"])
                    
                    vectors_to_upsert.append({
                        "id": chunk["id"],
                        "values": emb,
                        "metadata": sanitized_metadata  # Sanitized metadata compatible with Pinecone
                    })
                
                # Performing the upsert
                self.index.upsert(vectors=vectors_to_upsert)
                
                logger.info(f"Upserted batch {i//batch_size + 1}: {len(vectors_to_upsert)} vectors.")

            except Exception as e:
                logger.error(f"Failed to upsert batch starting at index {i}: {str(e)}")
                raise e

        logger.info(f"Vector ingestion complete. Total chunks upserted: {total_chunks}")

vector_service = VectorService()
