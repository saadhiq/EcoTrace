#!/usr/bin/env bash
# Build the Next.js static export and deploy it to Firebase Hosting.
# NEXT_PUBLIC_API_URL defaults to the deployed Cloud Run service URL.
# Usage: ./scripts/deploy-frontend.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-ecotrace-9e406}"
REGION="${REGION:-asia-south1}"
SERVICE="ecotrace-api"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "${NEXT_PUBLIC_API_URL:-}" ]]; then
  NEXT_PUBLIC_API_URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
fi
export NEXT_PUBLIC_API_URL
echo "Building with NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL"

cd "$REPO_ROOT/frontend"
npm ci --no-fund --no-audit
npm run build

cd "$REPO_ROOT"
firebase deploy --only hosting --project "$PROJECT_ID"
