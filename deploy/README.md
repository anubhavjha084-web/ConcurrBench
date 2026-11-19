# Deploying ConcurrencyBugBench API to Cloud Run

This guide walks through deploying the ConcurrencyBugBench API to Google Cloud Run.

## Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed and authenticated
- A GCP project with billing enabled
- Docker installed locally (for building images)
- API keys for the AI providers you want to use

## 1. Initial Setup

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"
gcloud config set project "$PROJECT_ID"

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  secretmanager.googleapis.com \
  containerregistry.googleapis.com \
  artifactregistry.googleapis.com
```

## 2. Create Secrets

Store API keys in Secret Manager:

```bash
# Bench API key (for authenticating requests to the API)
echo -n "your-secure-api-key" | \
  gcloud secrets create bench-api-key --data-file=-

# Provider API keys (add whichever you need)
echo -n "sk-..." | \
  gcloud secrets create openai-api-key --data-file=-

echo -n "sk-ant-..." | \
  gcloud secrets create anthropic-api-key --data-file=-

echo -n "AI..." | \
  gcloud secrets create google-api-key --data-file=-
```

## 3. Create a Service Account

```bash
# Create a dedicated service account
gcloud iam service-accounts create concurrency-bench-sa \
  --display-name="ConcurrencyBugBench API"

# Grant it access to secrets
for SECRET in bench-api-key openai-api-key anthropic-api-key google-api-key; do
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:concurrency-bench-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
```

## 4. Build and Push the Docker Image

### Option A: Push to GitHub Container Registry (CI/CD)

The CI pipeline automatically builds and pushes images on git tag pushes (`v*`).
Cloud Run can pull from `ghcr.io` if configured with appropriate credentials.

### Option B: Push to Google Artifact Registry

```bash
# Create an Artifact Registry repository
gcloud artifacts repositories create concurrency-bench \
  --repository-format=docker \
  --location=us-central1

# Build and push
docker build -f Dockerfile.api -t \
  us-central1-docker.pkg.dev/${PROJECT_ID}/concurrency-bench/api:latest .

docker push \
  us-central1-docker.pkg.dev/${PROJECT_ID}/concurrency-bench/api:latest
```

## 5. Deploy to Cloud Run

### Option A: Using the YAML Service Definition

Edit `cloudrun.yaml` to replace the placeholders:

| Placeholder  | Replace with                                       |
|--------------|---------------------------------------------------|
| `PROJECT_ID` | Your GCP project ID                                |
| `OWNER/REPO` | Your GitHub `owner/repo` (or Artifact Registry URI)|

Then deploy:

```bash
gcloud run services replace deploy/cloudrun.yaml \
  --region=us-central1
```

### Option B: Using the CLI Directly

```bash
gcloud run deploy concurrency-bug-bench-api \
  --image=us-central1-docker.pkg.dev/${PROJECT_ID}/concurrency-bench/api:latest \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --port=8000 \
  --cpu=1 \
  --memory=512Mi \
  --min-instances=0 \
  --max-instances=5 \
  --set-secrets="BENCH_API_KEY=bench-api-key:latest,OPENAI_API_KEY=openai-api-key:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest,GOOGLE_API_KEY=google-api-key:latest" \
  --service-account="concurrency-bench-sa@${PROJECT_ID}.iam.gserviceaccount.com"
```

## 6. Verify the Deployment

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe concurrency-bug-bench-api \
  --region=us-central1 --format='value(status.url)')

# Health check
curl "$SERVICE_URL/health"

# View API docs
echo "Open in browser: $SERVICE_URL/docs"
```

## 7. Monitoring

Cloud Run provides built-in monitoring via the GCP Console:

- **Logs**: Cloud Run → Select service → Logs tab
- **Metrics**: Request count, latency, container instance count
- **Prometheus**: The API exposes a `/metrics` endpoint for Prometheus scraping

## 8. Updating the Deployment

```bash
# After pushing a new image:
gcloud run services update concurrency-bug-bench-api \
  --image=us-central1-docker.pkg.dev/${PROJECT_ID}/concurrency-bench/api:latest \
  --region=us-central1
```

## Cost Considerations

- **Cloud Run**: Pay only for requests processed. With `minScale: 0`, there is no charge when idle.
- **Secret Manager**: First 10,000 access operations/month are free.
- **AI Provider API calls**: These are the main cost driver. Each evaluation run calls the AI provider for every task × trial combination.

## Security Notes

- API keys are stored in Secret Manager, never in environment variables or source code.
- The `BENCH_API_KEY` header (`X-API-Key`) is required for write endpoints (`POST /evaluate`).
- Consider restricting ingress to internal traffic or using Cloud IAM for production.
- Review CORS settings in `api/main.py` before production deployment.
