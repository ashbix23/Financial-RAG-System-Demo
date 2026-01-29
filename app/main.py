"""FastAPI application factory and entry point for the RAG production system."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.v1 import chat, ingest
from app.core.config import settings
from pinecone import Pinecone
from loguru import logger
import os


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Registers Chat and Ingestion routers, initializes Pinecone on startup,
    and exposes a health check endpoint. Loads settings from environment.

    Returns:
        FastAPI: The configured application instance.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        docs_url="/docs"
    )

    @app.on_event("startup")
    async def startup_event():
        """Initialize Pinecone connection and verify index exists on startup."""
        logger.info("Initializing Pinecone connection...")
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        
        # Check if index exists, log warning if not
        if settings.PINECONE_INDEX_NAME not in pc.list_indexes().names():
            logger.warning(f"Index {settings.PINECONE_INDEX_NAME} not found. Please create it in the console.")
        
        app.state.pinecone = pc
        logger.info("Application startup complete.")

    # Include Routers
    app.include_router(chat.router, prefix=settings.API_V1_STR, tags=["Chat"])
    app.include_router(ingest.router, prefix=settings.API_V1_STR, tags=["Ingestion"])

    @app.get("/health")
    async def health_check():
        """Return service health status and version."""
        return {"status": "healthy", "version": "1.0.0"}

    # Serve static files and UI
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
        
        @app.get("/")
        async def read_root():
            """Serve the main UI."""
            index_path = os.path.join(static_dir, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
            return {"message": "UI not found"}

    return app

app = create_app()
