#!/bin/bash
# Quick deployment script for Google Cloud Run

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN} RAG Production System - Cloud Run Deployment${NC}\n"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED} Error: .env file not found!${NC}"
    echo "Please create a .env file based on .env.example"
    exit 1
fi

# Load environment variables
set -a
source .env
set +a

# Check required variables
if [ -z "$ANTHROPIC_API_KEY" ] || [ -z "$COHERE_API_KEY" ] || [ -z "$PINECONE_API_KEY" ]; then
    echo -e "${RED} Error: Missing required API keys in .env file${NC}"
    echo "Required: ANTHROPIC_API_KEY, COHERE_API_KEY, PINECONE_API_KEY"
    exit 1
fi

# Get project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${YELLOW}  No Google Cloud project set.${NC}"
    read -p "Enter your Google Cloud Project ID: " PROJECT_ID
    gcloud config set project "$PROJECT_ID"
fi

echo -e "${GREEN}✓ Using project: $PROJECT_ID${NC}"

# Set region
REGION=${REGION:-us-central1}
echo -e "${GREEN}✓ Using region: $REGION${NC}\n"

# Build Docker image
echo -e "${YELLOW} Building Docker image...${NC}"
docker build -t gcr.io/$PROJECT_ID/rag-production-system:latest .

# Push to Container Registry
echo -e "${YELLOW} Pushing image to Container Registry...${NC}"
docker push gcr.io/$PROJECT_ID/rag-production-system:latest

# Prepare environment variables
ENV_VARS="ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY"
ENV_VARS="$ENV_VARS,COHERE_API_KEY=$COHERE_API_KEY"
ENV_VARS="$ENV_VARS,PINECONE_API_KEY=$PINECONE_API_KEY"
ENV_VARS="$ENV_VARS,LLM_MODEL=${LLM_MODEL:claude-haiku-4-5}"
ENV_VARS="$ENV_VARS,EMBEDDING_MODEL_NAME=${EMBEDDING_MODEL_NAME:-BAAI/bge-small-en-v1.5}"
ENV_VARS="$ENV_VARS,COHERE_RERANK_MODEL=${COHERE_RERANK_MODEL:-rerank-english-v3.0}"
ENV_VARS="$ENV_VARS,PINECONE_INDEX_NAME=${PINECONE_INDEX_NAME:-financial-rag-index}"
ENV_VARS="$ENV_VARS,PINECONE_DIMENSION=${PINECONE_DIMENSION:-384}"
ENV_VARS="$ENV_VARS,PINECONE_METRIC=${PINECONE_METRIC:-cosine}"
ENV_VARS="$ENV_VARS,CHUNK_SIZE=${CHUNK_SIZE:-1500}"
ENV_VARS="$ENV_VARS,CHUNK_OVERLAP=${CHUNK_OVERLAP:-200}"
ENV_VARS="$ENV_VARS,RETRIEVAL_LIMIT=${RETRIEVAL_LIMIT:-50}"
ENV_VARS="$ENV_VARS,RERANK_LIMIT=${RERANK_LIMIT:-10}"
ENV_VARS="$ENV_VARS,ALLOWED_EXTENSIONS=${ALLOWED_EXTENSIONS:-.pdf,.txt,.html}"
ENV_VARS="$ENV_VARS,MAX_UPLOAD_MB=${MAX_UPLOAD_MB:-50}"
ENV_VARS="$ENV_VARS,PROJECT_NAME=${PROJECT_NAME:-Financial RAG System}"
ENV_VARS="$ENV_VARS,API_V1_STR=${API_V1_STR:-/api/v1}"

# Deploy to Cloud Run
echo -e "${YELLOW} Deploying to Cloud Run...${NC}"
gcloud run deploy rag-production-system \
  --image gcr.io/$PROJECT_ID/rag-production-system:latest \
  --platform managed \
  --region $REGION \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --set-env-vars "$ENV_VARS" \
  --allow-unauthenticated

# Get service URL
SERVICE_URL=$(gcloud run services describe rag-production-system --region $REGION --format 'value(status.url)')

echo -e "\n${GREEN} Deployment complete!${NC}\n"
echo -e "Service URL: ${GREEN}$SERVICE_URL${NC}\n"
echo -e "Test it with:"
echo -e "  curl $SERVICE_URL/health"
echo -e "\n${YELLOW}💡 Tip: Set min instances > 0 to avoid cold starts${NC}"
echo -e "  gcloud run services update rag-production-system --min-instances 1 --region $REGION"
