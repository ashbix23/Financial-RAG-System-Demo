"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pydantic settings for API keys, model config, and RAG hyperparameters.

    All values are loaded from the .env file. Required keys must be set
    in the environment. Optional fields have defaults.
    """
    # --- Project Metadata ---
    PROJECT_NAME: str = "Financial RAG System (Pinecone)"
    API_V1_STR: str = "/api/v1"
    
    # --- API Keys ---
    ANTHROPIC_API_KEY: str
    COHERE_API_KEY: str
    PINECONE_API_KEY: str
    
    # --- Pinecone Config ---
    PINECONE_INDEX_NAME: str = "financial-rag-index"
    PINECONE_DIMENSION: int = 384  # Match BGE-Small (bge-small-en-v1.5) output
    PINECONE_METRIC: str = "cosine"
    
    # --- Model Selection ---
    LLM_MODEL: str = "claude-haiku-4-5"
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"  # SentenceTransformer model for embeddings
    COHERE_RERANK_MODEL: str = "rerank-english-v3.0"
    
    # --- RAG Hyperparameters ---
    CHUNK_SIZE: int = 1500
    CHUNK_OVERLAP: int = 200
    RETRIEVAL_LIMIT: int = 50  # Fetch more for Cohere to look at
    RERANK_LIMIT: int = 10    # Final count for the LLM context

    # --- Ingestion ---
    ALLOWED_EXTENSIONS: str = ".pdf,.txt,.html"
    MAX_UPLOAD_MB: int = 50
    
    # --- Application Settings ---
    ENVIRONMENT: str = "production"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()
