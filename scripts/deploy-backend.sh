#!/usr/bin/env bash
# Build (Cloud Build) and deploy the FastAPI backend to Cloud Run.
# Usage: ./scripts/deploy-backend.sh
# Extra gcloud flags (e.g. a no-traffic tagged test revision):
#   EXTRA_DEPLOY_FLAGS="--tag failtest --no-traffic" GEMINI_TIMEOUT_S=0.001 ./scripts/deploy-backend.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-ecotrace-9e406}"
REGION="${REGION:-asia-south1}"
SERVICE="ecotrace-api"
RUNTIME_SA="ecotrace-backend@${PROJECT_ID}.iam.gserviceaccount.com"
ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-http://localhost:3000,https://${PROJECT_ID}.web.app,https://${PROJECT_ID}.firebaseapp.com}"
# Gemini on Vertex AI (see backend/app/config.py) and the private photo bucket.
GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.5-flash}"
GEMINI_LOCATION="${GEMINI_LOCATION:-asia-south1}"
GEMINI_THINKING_LEVEL="${GEMINI_THINKING_LEVEL:-minimal}"
GEMINI_TIMEOUT_S="${GEMINI_TIMEOUT_S:-25}"
PHOTO_BUCKET="${PHOTO_BUCKET:-${PROJECT_ID}-bag-photos}"

ENV_VARS="ALLOWED_ORIGINS=${ALLOWED_ORIGINS}@GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
ENV_VARS+="@GEMINI_MODEL=${GEMINI_MODEL}@GEMINI_LOCATION=${GEMINI_LOCATION}"
ENV_VARS+="@GEMINI_THINKING_LEVEL=${GEMINI_THINKING_LEVEL}@GEMINI_TIMEOUT_S=${GEMINI_TIMEOUT_S}"
ENV_VARS+="@PHOTO_BUCKET=${PHOTO_BUCKET}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck disable=SC2086 # EXTRA_DEPLOY_FLAGS is intentionally word-split
gcloud run deploy "$SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --source "$REPO_ROOT/backend" \
  --service-account "$RUNTIME_SA" \
  --allow-unauthenticated \
  --min-instances 0 \
  --set-env-vars "^@^${ENV_VARS}" \
  ${EXTRA_DEPLOY_FLAGS:-} \
  --quiet

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
echo "Deployed: $URL"
curl -fsS "$URL/health" && echo
