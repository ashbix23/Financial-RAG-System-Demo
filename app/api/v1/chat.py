"""RAG query API: retrieve context, rerank, and generate answers."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.search import search_service
from app.services.llm import llm_service
from loguru import logger

router = APIRouter()


class ChatRequest(BaseModel):
    """Request body for RAG query endpoint."""

    query: str
    user_id: str = "default_user"


class ChatResponse(BaseModel):
    """Response body for RAG query endpoint."""

    answer: str
    status: str = "success"


@router.post("/query", response_model=ChatResponse)
async def query_rag(request: ChatRequest):
    """Run the RAG pipeline: retrieve, rerank, and generate.

    Fetches relevant chunks from Pinecone (filtered by user_id), reranks
    with Cohere, then generates an answer via Claude. Returns a fallback
    message if no context is found. On errors, returns ChatResponse with
    status="error" and a user-friendly message (does not raise).

    Args:
        request: ChatRequest with query and user_id.

    Returns:
        ChatResponse with answer and status (success or error).
    """
    try:
        # RETRIEVAL & RERANKING
        context = await search_service.get_context(
            query=request.query, 
            user_id=request.user_id
        )
        
        if not context:
            return ChatResponse(
                answer="I couldn't find any relevant documents to answer your question."
            )

        # GENERATION
        answer = await llm_service.generate_answer(
            query=request.query, 
            context=context
        )
        
        return ChatResponse(answer=answer)

    except Exception as e:
        logger.error(f"Chat request failed: {type(e).__name__}: {str(e)}", exc_info=True)
        raw = str(e)[:200].strip()
        # Avoid showing raw key/attribute names (e.g. KeyError('type') -> "'type'" or '"type"')
        if not raw:
            answer = "An error occurred while processing your query. Please try again."
        elif len(raw) < 50 and (
            (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"'))
        ):
            answer = "An error occurred while processing your query. Please try again."
        else:
            answer = f"Error processing your query: {raw}"
        return ChatResponse(
            answer=answer,
            status="error"
        )