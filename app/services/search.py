"""Semantic search and reranking for RAG retrieval."""

import cohere
from loguru import logger
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

from app.core.config import settings


class SearchService:
    """Run embed -> Pinecone -> Cohere rerank for RAG context retrieval.

    Uses the same SentenceTransformer as ingestion for query embeddings.
    Filters by user_id for multi-tenancy.
    """

    def __init__(self) -> None:
        """Load embedding model, Cohere client, and Pinecone index."""
        logger.info(f"Loading embedding model for search: {settings.EMBEDDING_MODEL_NAME}...")
        self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        self.cohere_client = cohere.Client(api_key=settings.COHERE_API_KEY)
        self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index = self.pc.Index(settings.PINECONE_INDEX_NAME)
        logger.info("Search service initialized.")

    async def get_context(self, query: str, user_id: str) -> str:
        """Embed query, search Pinecone, rerank with Cohere, and return context.

        Fetches up to RETRIEVAL_LIMIT matches (user_id filter), reranks to
        RERANK_LIMIT, then joins chunk text with newlines and "---" separators.

        Args:
            query: User search query.
            user_id: Tenant ID for metadata filtering.

        Returns:
            Joined context string for the LLM, or "" if no matches.
        """
        try:
            # Generating query embedding using SentenceTransformer (matches ingestion)
            logger.debug(f"Generating embedding for query: {query[:50]}...")
            query_emb = self.embedding_model.encode(query, convert_to_numpy=True).tolist()

            # Semantic Search in Pinecone with Metadata Filtering
            logger.debug(f"Querying Pinecone with user_id filter: {user_id}")
            search_results = self.index.query(
                vector=query_emb,
                top_k=settings.RETRIEVAL_LIMIT,
                include_metadata=True,
                filter={"user_id": {"$eq": user_id}}
            )

            if not search_results.get('matches'):
                logger.info(f"No matches found in Pinecone for query: {query[:50]}... (user_id: {user_id})")
                return ""

            logger.info(f"Found {len(search_results['matches'])} matches in Pinecone")

            # Preparing documents for Cohere Rerank
            chunks = []
            for match in search_results['matches']:
                try:
                    chunk_text = match['metadata'].get('text', '')
                    if chunk_text:
                        chunks.append(chunk_text)
                except Exception as e:
                    logger.warning(f"Error extracting text from match: {str(e)}")
                    continue

            if not chunks:
                logger.warning("No valid chunks extracted from Pinecone matches")
                return ""

            # Cohere Reranking
            logger.debug(f"Reranking {len(chunks)} chunks with Cohere...")
            reranked_results = self.cohere_client.rerank(
                query=query,
                documents=chunks,
                top_n=settings.RERANK_LIMIT,
                model=settings.COHERE_RERANK_MODEL
            )

            # Extracting the final top documents
            final_context_chunks = []
            for result in reranked_results.results:
                final_context_chunks.append(chunks[result.index])

            logger.info(f"Retrieved {len(chunks)} chunks, reranked down to {len(final_context_chunks)}")
            
            # Joining chunks with newlines for the LLM prompt
            return "\n\n---\n\n".join(final_context_chunks)
            
        except Exception as e:
            logger.error(f"Error in search/retrieval pipeline: {str(e)}", exc_info=True)
            raise

search_service = SearchService()
