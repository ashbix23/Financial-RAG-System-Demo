# RAG Production System

A production-ready **Retrieval-Augmented Generation (RAG)** system that lets you upload documents (PDF, TXT, HTML) and ask questions against them. It uses Pinecone for vector storage, Cohere for reranking, and Claude (Anthropic) for answer generation.

## Features

- **Document ingestion**: Upload PDF, TXT, or HTML; documents are parsed, chunked, embedded (BGE-Small), and stored in Pinecone.
- **RAG chat**: Query your documents; the system retrieves relevant chunks, reranks with Cohere, and generates answers with Claude Haiku 4.5.
- **Multi-tenancy**: Data is isolated by `user_id`; each user only sees their own documents.
- **Status API**: Check whether a document has finished processing before querying (`GET /api/v1/status/{file_id}`).
- **Web UI**: Simple chat interface served at `/` (or use the API directly).

## Prerequisites

- **Python 3.11** (or 3.12)
- **Docker** (optional, for containerized run)
- API keys:
  - [Anthropic](https://console.anthropic.com/) (Claude)
  - [Cohere](https://dashboard.cohere.com/) (reranking)
  - [Pinecone](https://app.pinecone.io/) (vector index)

Create a Pinecone index with dimension **384** and metric **cosine** (for BGE-Small). Index name defaults to `financial-rag-index` (configurable via `PINECONE_INDEX_NAME`).

## Quick Start (Local)

1. **Clone and install**

   ```bash
   cd rag-production-system
   pip install -r requirements.txt
   ```

2. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env and set ANTHROPIC_API_KEY, COHERE_API_KEY, PINECONE_API_KEY
   # Use LLM_MODEL=claude-haiku-4-5 (see .env.example)
   ```

3. **Run the app**

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Open http://localhost:8000 for the UI, or http://localhost:8000/docs for the API docs.

## Quick Start (Docker)

```bash
# Build and run with docker-compose (uses .env for API keys)
docker-compose up --build
```

The app will be at http://localhost:8000. Ensure `.env` has the required keys and `LLM_MODEL=claude-haiku-4-5`.

## API Overview

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Web UI (chat interface) |
| GET | `/health` | Health check |
| GET | `/docs` | OpenAPI (Swagger) docs |
| POST | `/api/v1/upload` | Upload a document (multipart: `file`, `user_id`) |
| GET | `/api/v1/status/{file_id}` | Check if document processing completed |
| POST | `/api/v1/query` | RAG query (JSON: `query`, `user_id`) |

## Configuration

Key settings are in `.env` (see `.env.example`). Important:

- **LLM_MODEL**: Use `claude-haiku-4-5` (invalid: `claude-4-5-haiku-20251015`).
- **PINECONE_INDEX_NAME**, **PINECONE_DIMENSION** (384), **PINECONE_METRIC** (cosine) must match your Pinecone index.
- **CHUNK_SIZE**, **CHUNK_OVERLAP**, **RETRIEVAL_LIMIT**, **RERANK_LIMIT** control chunking and retrieval.

## Project Layout

```
rag-production-system/
├── app/
│   ├── main.py
│   ├── api/v1/
│   │   ├── chat.py
│   │   └── ingest.py
│   ├── core/
│   │   └── config.py
│   ├── services/
│   │   ├── document.py
│   │   ├── vector.py
│   │   ├── search.py
│   │   └── llm.py
│   └── static/
│       └── index.html
├── tests/
├── evaluation/
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt
├── deploy-cloud-run.sh
├── cloudbuild.yaml
└── DEPLOYMENT.md
```

- `app/main.py` – FastAPI app and routes
- `app/api/v1/` – Chat and ingest API handlers
- `app/services/` – Document parsing, vector upsert, search, LLM
- `app/core/config.py` – Settings from environment
- `app/static/` – Web UI (single-page chat)

## License

MIT. See [LICENSE](LICENSE).
