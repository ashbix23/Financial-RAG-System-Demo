"""Document parsing and chunking for RAG ingestion."""

import uuid
from typing import List

from langchain_community.document_loaders import UnstructuredFileLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from app.core.config import settings


class DocumentService:
    """Parse documents and split them into chunks for embedding and storage."""

    def __init__(self) -> None:
        """Initialize the text splitter from config (chunk size, overlap, separators)."""
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

    async def process_file(self, file_path: str, metadata: dict) -> List[dict]:
        """Parse a file, chunk it, and format chunks for Pinecone upsert.

        Uses UnstructuredFileLoader (elements mode) and RecursiveCharacterTextSplitter.
        Each chunk gets a unique id (file_id#chunk{i}) and metadata merged with
        chunk metadata (including user_id, filename, and raw text).

        Args:
            file_path: Path to the file (PDF, TXT, HTML).
            metadata: Dict with file_id, filename, user_id, extension.

        Returns:
            List of dicts with keys id, text, metadata (ready for vector_service).
        """
        logger.info(f"Processing file: {file_path}")
        
        # Loading and Parsing
        loader = UnstructuredFileLoader(file_path, mode="elements")
        docs = loader.load()
        
        # Extracting and Chunking
        chunks = self.text_splitter.split_documents(docs)
        
        processed_chunks = []
        for i, chunk in enumerate(chunks):
            # Create a unique ID for each chunk to prevent collisions in Pinecone
            chunk_id = f"{metadata.get('file_id', str(uuid.uuid4()))}#chunk{i}"
            
            # Safely merge chunk metadata (handle any KeyErrors or type issues)
            chunk_metadata = {}
            if hasattr(chunk, 'metadata') and chunk.metadata:
                try:
                    # Filter out None values and ensure all keys are strings
                    chunk_metadata = {
                        str(k): v for k, v in chunk.metadata.items() 
                        if v is not None and isinstance(k, (str, int, float))
                    }
                except Exception as e:
                    logger.warning(f"Error processing chunk {i} metadata: {str(e)}")
                    # Continue with empty chunk_metadata if there's an error
            
            # Merge metadata: chunk metadata first, then our metadata (our metadata takes precedence)
            merged_metadata = {
                **chunk_metadata,
                **metadata,  # Including user_id, file_id, filename, etc.
                "text": chunk.page_content
            }
            
            processed_chunks.append({
                "id": chunk_id,
                "text": chunk.page_content,
                "metadata": merged_metadata
            })
            
        logger.info(f"Split document into {len(processed_chunks)} chunks.")
        return processed_chunks

document_service = DocumentService()
