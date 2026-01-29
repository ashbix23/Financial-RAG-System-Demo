"""Document upload and background ingestion API."""

import os
import shutil
import uuid

from fastapi import APIRouter, File, HTTPException, BackgroundTasks, Request, UploadFile, Form
from loguru import logger
from pinecone import Pinecone

from app.core.config import settings
from app.services.document import document_service
from app.services.vector import vector_service

router = APIRouter()

_MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024
_ALLOWED_EXTENSIONS = {e.strip().lower() for e in settings.ALLOWED_EXTENSIONS.split(",") if e.strip()}


async def run_ingestion_pipeline(file_path: str, metadata: dict) -> None:
    """Run the ingestion pipeline: parse, chunk, embed, and upsert to Pinecone.

    Processes the file at file_path, then deletes it. Failures are logged;
    the temp file is always removed in a finally block.

    Args:
        file_path: Path to the saved upload (e.g. data/temp/{uuid}.pdf).
        metadata: Dict with file_id, filename, user_id, extension.

    Raises:
        Exception: Re-raised after logging on parse, embed, or upsert failure.
    """
    file_id = metadata.get('file_id', 'unknown')
    filename = metadata.get('filename', 'unknown')
    user_id = metadata.get('user_id', 'unknown')
    
    try:
        logger.info(f"Starting ingestion pipeline for file_id={file_id}, filename={filename}, user_id={user_id}")
        
        # 1. Parsing and Chunking
        logger.info(f"Step 1/3: Parsing and chunking document: {file_path}")
        chunks = await document_service.process_file(file_path, metadata)
        
        if not chunks:
            logger.warning(f"No chunks generated from {file_path}. File may be empty or unparseable.")
            return
        
        logger.info(f"Step 2/3: Generated {len(chunks)} chunks from document")
        
        # Embedding and Upserting
        logger.info(f"Step 3/3: Generating embeddings and upserting to Pinecone...")
        await vector_service.upsert_chunks(chunks)
        
        logger.info(
            f"Successfully ingested document: file_id={file_id}, filename={filename}, "
            f"user_id={user_id}, chunks={len(chunks)}"
        )
        
    except Exception as e:
        logger.error(
            f"Background ingestion FAILED for file_id={file_id}, filename={filename}, "
            f"user_id={user_id}: {str(e)}",
            exc_info=True  # Include full traceback
        )
        # Re-raise to ensure the error is visible in logs
        raise
    
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.debug(f"Cleaned up temporary file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temp file {file_path}: {str(e)}")

@router.post("/upload")
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Form("default_user"),
):
    """Accept a document, save it temporarily, and run ingestion in the background.

    Validates file type (from ALLOWED_EXTENSIONS) and size (MAX_UPLOAD_MB),
    streams to data/temp, then enqueues run_ingestion_pipeline. Returns immediately with file_id.

    Args:
        request: FastAPI request (used for Content-Length check).
        background_tasks: FastAPI background tasks runner.
        file: Uploaded file (required).
        user_id: Tenant/user identifier for multi-tenancy (default: default_user).

    Returns:
        Dict with status, file_id, and message.

    Raises:
        HTTPException: 400 unsupported file type, 413 payload too large, 500 save failure.
    """
    try:
        # Validate size (when Content-Length present)
        cl = request.headers.get("content-length")
        if cl:
            try:
                if int(cl) > _MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_MB} MB",
                    )
            except ValueError:
                pass  # Malformed Content-Length; skip size check

        # Validate file type
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="No filename provided"
            )
        
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in _ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {sorted(_ALLOWED_EXTENSIONS)}",
            )

        # Ensure directory exists with proper path handling
        temp_dir = os.path.join(os.getcwd(), "data", "temp")
        os.makedirs(temp_dir, exist_ok=True)
        temp_file_id = str(uuid.uuid4())
        file_path = os.path.join(temp_dir, f"{temp_file_id}{ext}")

        # Streaming to Disk (Efficient for large files)
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            logger.error(f"File save failed: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")

        # Preparing Metadata (Critical for Multi-tenancy)
        metadata = {
            "file_id": temp_file_id,
            "filename": file.filename,
            "user_id": user_id,
            "extension": ext
        }

        # Offloading to Background Tasks
        background_tasks.add_task(run_ingestion_pipeline, file_path, metadata)

        return {
            "status": "ingestion_started",
            "file_id": temp_file_id,
            "message": "Your document is being processed and will be available for chat shortly."
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions (400, 413, etc.)
        raise
    except Exception as e:
        logger.error(f"Upload endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/status/{file_id}")
async def get_processing_status(file_id: str, user_id: str = "default_user"):
    """Check the processing status of an uploaded document.
    
    Queries Pinecone to see if chunks exist for the given file_id.
    This indicates whether document processing has completed successfully.
    
    Args:
        file_id: The file_id returned from the upload endpoint.
        user_id: The user_id used during upload (default: default_user).
    
    Returns:
        Dict with status ("processing", "completed", or "not_found") and chunk_count.
    """
    try:
        # Initialize Pinecone connection
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        index = pc.Index(settings.PINECONE_INDEX_NAME)
        
        # Query Pinecone with metadata filter to check if chunks exist for this file_id
        # Use a dummy zero vector since we only care about metadata filtering
        dummy_vector = [0.0] * settings.PINECONE_DIMENSION
        
        try:
            search_results = index.query(
                vector=dummy_vector,
                top_k=1,  # We only need to know if any chunks exist
                include_metadata=True,
                filter={
                    "file_id": {"$eq": file_id},
                    "user_id": {"$eq": user_id}
                }
            )
            
            if search_results.get('matches') and len(search_results['matches']) > 0:
                # Chunks exist - document processing completed
                # Count total chunks by querying with higher top_k
                count_results = index.query(
                    vector=dummy_vector,
                    top_k=10000,  # Max reasonable limit to count chunks
                    include_metadata=False,
                    filter={
                        "file_id": {"$eq": file_id},
                        "user_id": {"$eq": user_id}
                    }
                )
                chunk_count = len(count_results.get('matches', []))
                
                return {
                    "status": "completed",
                    "file_id": file_id,
                    "user_id": user_id,
                    "chunk_count": chunk_count,
                    "message": f"Document processing completed successfully. {chunk_count} chunks indexed."
                }
            else:
                # No chunks found - still processing or failed
                return {
                    "status": "processing",
                    "file_id": file_id,
                    "user_id": user_id,
                    "chunk_count": 0,
                    "message": "Document is still being processed. Please wait and check again."
                }
                
        except Exception as query_error:
            logger.error(f"Error querying Pinecone for file_id={file_id}: {str(query_error)}")
            return {
                "status": "processing",
                "file_id": file_id,
                "user_id": user_id,
                "chunk_count": 0,
                "message": "Unable to determine status. Document may still be processing."
            }
            
    except Exception as e:
        logger.error(f"Status check failed for file_id={file_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check processing status: {str(e)}"
        )
