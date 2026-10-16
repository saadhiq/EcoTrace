#!/usr/bin/env bash
# Build (Cloud Build) and deploy the FastAPI backend to Cloud Run.
# Usage: ./scripts/deploy-backend.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-ecotrace-9e406}"
REGION="${REGION:-asia-south1}"
SERVICE="ecotrace-api"
RUNTIME_SA="ecotrace-backend@${PROJECT_ID}.iam.gserviceaccount.com"
ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-http://localhost:3000,https://${PROJECT_ID}.web.app,https://${PROJECT_ID}.firebaseapp.com}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

gcloud run deploy "$SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --source "$REPO_ROOT/backend" \
  --service-account "$RUNTIME_SA" \
  --allow-unauthenticated \
  --min-instances 0 \
  --set-env-vars "^@^ALLOWED_ORIGINS=${ALLOWED_ORIGINS}" \
  --quiet

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
echo "Deployed: $URL"
curl -fsS "$URL/health" && echo
