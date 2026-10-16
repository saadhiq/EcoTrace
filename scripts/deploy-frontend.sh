#!/usr/bin/env bash
# Build the Next.js static export and deploy it to Firebase Hosting.
# Build-time env is filled automatically:
#   NEXT_PUBLIC_API_URL          <- Cloud Run service URL
#   NEXT_PUBLIC_FIREBASE_*       <- `firebase apps:sdkconfig` for the web app
# Usage: ./scripts/deploy-frontend.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-ecotrace-9e406}"
REGION="${REGION:-asia-south1}"
SERVICE="ecotrace-api"
WEB_APP_ID="${FIREBASE_WEB_APP_ID:-1:55962094566:web:eff857d7171aac9606e427}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "${NEXT_PUBLIC_API_URL:-}" ]]; then
  NEXT_PUBLIC_API_URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
fi
export NEXT_PUBLIC_API_URL

# Firebase web config is public, but we keep it out of git and fetch it here.
SDK_JSON="$(firebase apps:sdkconfig web "$WEB_APP_ID" --project "$PROJECT_ID" --json)"
eval "$(node -e '
  const j = JSON.parse(process.argv[1]);
  const c = j.result.sdkConfig || j.result;
  const map = {
    API_KEY: c.apiKey, AUTH_DOMAIN: c.authDomain, PROJECT_ID: c.projectId,
    APP_ID: c.appId, STORAGE_BUCKET: c.storageBucket, MESSAGING_SENDER_ID: c.messagingSenderId,
  };
  for (const [k, v] of Object.entries(map)) {
    if (!v && k !== "STORAGE_BUCKET") throw new Error("missing " + k);
    console.log(`export NEXT_PUBLIC_FIREBASE_${k}=${JSON.stringify(v || "")}`);
  }
' "$SDK_JSON")"

echo "Building with NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL (Firebase project $NEXT_PUBLIC_FIREBASE_PROJECT_ID)"

cd "$REPO_ROOT/frontend"
npm ci --no-fund --no-audit
npm run build

cd "$REPO_ROOT"
firebase deploy --only hosting --project "$PROJECT_ID"
