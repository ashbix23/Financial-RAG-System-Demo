# Deployment Guide - Google Cloud Run

This guide covers deploying the RAG Production System to Google Cloud Run. For project overview, local run, and API details, see [README.md](README.md).

## Prerequisites

**Phase 1 Complete** - The following should already be set up:
- Google Cloud account with billing enabled
- `gcloud` CLI installed and authenticated (`gcloud auth login`)
- Project created and set (`gcloud config set project YOUR_PROJECT_ID`)
- Required APIs enabled:
  - Cloud Run API
  - Container Registry API
  - Cloud Build API (optional, for CI/CD)
- Docker authentication configured (`gcloud auth configure-docker`)

## Resource Requirements

- **Memory**: Minimum 2GB RAM (for Sentence Transformers model + PDF processing)
- **CPU**: 2+ cores recommended
- **Storage**: ~500MB for dependencies and models
- **Timeout**: 300 seconds (for large file processing)

## Quick Start Deployment

### Option 1: Using Deployment Script (Recommended)

The easiest way to deploy is using the provided script:

```bash
./deploy-cloud-run.sh
```

This script will:
1. Verify your `.env` file exists
2. Load environment variables from `.env`
3. Build the Docker image
4. Push to Container Registry
5. Deploy to Cloud Run with proper configuration
6. Output your service URL

**Requirements**: Ensure your `.env` file has all required API keys:
- `ANTHROPIC_API_KEY`
- `COHERE_API_KEY`
- `PINECONE_API_KEY`

### Option 2: Manual Deployment

#### Step 1: Build and Push Docker Image

```bash
# Set your project ID
PROJECT_ID=$(gcloud config get-value project)

# Build the image
docker build -t gcr.io/$PROJECT_ID/rag-production-system:latest .

# Push to Container Registry
docker push gcr.io/$PROJECT_ID/rag-production-system:latest
```

#### Step 2: Deploy to Cloud Run

```bash
gcloud run deploy rag-production-system \
  --image gcr.io/$PROJECT_ID/rag-production-system:latest \
  --platform managed \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --set-env-vars "ANTHROPIC_API_KEY=your_key,COHERE_API_KEY=your_key,PINECONE_API_KEY=your_key" \
  --allow-unauthenticated
```

#### Step 3: Set Additional Environment Variables (Optional)

If you need to set additional configuration:

```bash
gcloud run services update rag-production-system \
  --update-env-vars "LLM_MODEL=claude-haiku-4-5,EMBEDDING_MODEL_NAME=BAAI/bge-small-en-v1.5,PINECONE_INDEX_NAME=financial-rag-index" \
  --region us-central1
```

## Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude LLM | `sk-ant-...` |
| `COHERE_API_KEY` | Cohere API key for reranking | `...` |
| `PINECONE_API_KEY` | Pinecone API key for vector database | `...` |

### Optional Variables (with defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | `claude-haiku-4-5` | Anthropic model name (Claude Haiku 4.5) |
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-small-en-v1.5` | Sentence Transformer model |
| `COHERE_RERANK_MODEL` | `rerank-english-v3.0` | Cohere reranking model |
| `PINECONE_INDEX_NAME` | `financial-rag-index` | Pinecone index name |
| `PINECONE_DIMENSION` | `384` | Vector dimension |
| `PINECONE_METRIC` | `cosine` | Similarity metric |
| `CHUNK_SIZE` | `1500` | Text chunk size |
| `CHUNK_OVERLAP` | `200` | Chunk overlap |
| `RETRIEVAL_LIMIT` | `50` | Initial retrieval count |
| `RERANK_LIMIT` | `10` | Final reranked count |
| `ALLOWED_EXTENSIONS` | `.pdf,.txt,.html` | Allowed file types |
| `MAX_UPLOAD_MB` | `50` | Max upload size |
| `PROJECT_NAME` | `Financial RAG System` | Application name |
| `API_V1_STR` | `/api/v1` | API prefix |

## Testing Deployment

After deployment, test your endpoints:

```bash
# Get your service URL
SERVICE_URL=$(gcloud run services describe rag-production-system \
  --region us-central1 \
  --format 'value(status.url)')

# Health check
curl $SERVICE_URL/health

# Chat endpoint (example)
curl -X POST $SERVICE_URL/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is this document about?", "user_id": "test_user"}'
```

## Using Cloud Build (CI/CD)

For automated deployments on git push:

### Step 1: Create Cloud Build Trigger

1. Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers)
2. Click "Create Trigger"
3. Connect your repository (GitHub, GitLab, etc.)
4. Select `cloudbuild.yaml` as the configuration file
5. Set substitution variables for secrets:
   - `_ANTHROPIC_API_KEY`
   - `_COHERE_API_KEY`
   - `_PINECONE_API_KEY`
   - (Optional: other config variables)

### Step 2: Push to Trigger Build

```bash
git push origin main
```

Cloud Build will automatically:
- Build the Docker image
- Push to Container Registry
- Deploy to Cloud Run

## Troubleshooting

### Out of Memory Errors

**Symptoms**: Container crashes or requests fail with memory errors

**Solutions**:
- Increase memory allocation:
  ```bash
  gcloud run services update rag-production-system \
    --memory 4Gi \
    --region us-central1
  ```
- Consider using a lighter embedding model
- Optimize batch sizes in `app/services/vector.py`

### Slow Startup / Cold Starts

**Symptoms**: First request takes 30+ seconds

**Solutions**:
- Set minimum instances to keep containers warm:
  ```bash
  gcloud run services update rag-production-system \
    --min-instances 1 \
    --region us-central1
  ```
- Pre-warm the service by calling `/health` endpoint periodically
- Consider using Cloud Run's min instances feature

### PDF Processing Issues

**Symptoms**: PDF uploads fail or return empty content

**Solutions**:
- Verify system dependencies are installed (check Dockerfile)
- Check unstructured library version compatibility
- Ensure PDFs are not password-protected or corrupted
- Review logs: `gcloud run services logs read rag-production-system --region us-central1`

### Port Binding Errors

**Symptoms**: Container fails to start, port already in use

**Solutions**:
- Verify Dockerfile uses `${PORT:-8000}` syntax
- Cloud Run sets PORT automatically - don't hardcode it
- Check CMD in Dockerfile uses shell form: `sh -c "..."`

### Environment Variables Not Set

**Symptoms**: API calls fail with authentication errors

**Solutions**:
- Verify env vars are set:
  ```bash
  gcloud run services describe rag-production-system \
    --region us-central1 \
    --format 'value(spec.template.spec.containers[0].env)'
  ```
- Update env vars:
  ```bash
  gcloud run services update rag-production-system \
    --update-env-vars "ANTHROPIC_API_KEY=new_key" \
    --region us-central1
  ```

### Model Download Issues

**Symptoms**: Slow first request, model not loading

**Solutions**:
- Sentence Transformers downloads models on first use
- This is normal - subsequent requests will be faster
- Consider pre-warming with min instances
- Models are cached in container filesystem

## Cost Optimization Tips

### 1. Use Scale-to-Zero

Cloud Run scales to zero when not in use (default behavior). This means:
- No charges when idle
- Only pay for actual request processing time

### 2. Set Max Instances

Limit maximum instances to control costs:

```bash
gcloud run services update rag-production-system \
  --max-instances 5 \
  --region us-central1
```

### 3. Optimize Memory Allocation

Start with minimum required memory and increase if needed:

```bash
# Test with 1Gi first
gcloud run services update rag-production-system \
  --memory 1Gi \
  --region us-central1
```

### 4. Use Free Tier

Google Cloud Run free tier includes:
- 2 million requests/month
- 360,000 GB-seconds
- 180,000 vCPU-seconds

### 5. Monitor Usage

Set up billing alerts:
1. Go to [Billing](https://console.cloud.google.com/billing)
2. Create budget alerts
3. Set thresholds (e.g., $10, $50, $100)

## Updating Deployment

### Update Code and Redeploy

```bash
# Make your code changes
# Then redeploy:
./deploy-cloud-run.sh
```

Or manually:

```bash
docker build -t gcr.io/$PROJECT_ID/rag-production-system:latest .
docker push gcr.io/$PROJECT_ID/rag-production-system:latest
gcloud run deploy rag-production-system \
  --image gcr.io/$PROJECT_ID/rag-production-system:latest \
  --region us-central1
```

### Rollback to Previous Revision

```bash
# List revisions
gcloud run revisions list --service rag-production-system --region us-central1

# Rollback to specific revision
gcloud run services update-traffic rag-production-system \
  --to-revisions REVISION_NAME=100 \
  --region us-central1
```

## Monitoring and Logs

### View Logs

```bash
# Stream logs
gcloud run services logs tail rag-production-system --region us-central1

# View recent logs
gcloud run services logs read rag-production-system --region us-central1 --limit 50
```

### Monitor Metrics

1. Go to [Cloud Run Console](https://console.cloud.google.com/run)
2. Click on your service
3. View metrics:
   - Request count
   - Latency
   - Error rate
   - Memory/CPU usage

## Security Best Practices

1. **Use Secret Manager** (recommended for production):
   ```bash
   # Store secrets
   echo -n "your-api-key" | gcloud secrets create anthropic-api-key --data-file=-
   
   # Grant Cloud Run access
   gcloud secrets add-iam-policy-binding anthropic-api-key \
     --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   
   # Use in deployment
   gcloud run services update rag-production-system \
     --update-secrets ANTHROPIC_API_KEY=anthropic-api-key:latest \
     --region us-central1
   ```

2. **Restrict Access** (remove `--allow-unauthenticated`):
   ```bash
   gcloud run services update rag-production-system \
     --no-allow-unauthenticated \
     --region us-central1
   ```

3. **Use IAM** for fine-grained access control

## Next Steps

- Set up monitoring and alerts
- Configure custom domain (optional)
- Set up CI/CD with Cloud Build
- Implement secret management for production
- Configure auto-scaling policies

## Support

For issues specific to:
- **Google Cloud Run**: [Cloud Run Documentation](https://cloud.google.com/run/docs)
- **This Application**: Check logs and troubleshooting section above
