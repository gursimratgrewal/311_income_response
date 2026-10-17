#!/usr/bin/env bash
# gcloud_command.sh, webapp only
# 1. Store the service account key in Secret Manager
# 2. Read the API service URL, if that service is deployed
# 3. Deploy the Streamlit service with the key mounted
#
# To run from this directory:
#   bash streamlit_cloud_command.sh
# Tear down:
#   bash streamlit_cloud_command.sh teardown
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/streamlit_config.sh"

gcloud config set project "$PROJECT_ID"
gcloud config set run/region "$REGION"

if [ "${1:-}" = "teardown" ]; then
  gcloud run services delete "$WEBAPP_SERVICE" --region "$REGION" --quiet
  echo "Deleted $WEBAPP_SERVICE."
  exit 0
fi

# GCS secret key
gcloud services enable secretmanager.googleapis.com run.googleapis.com \
  cloudbuild.googleapis.com

if ! gcloud secrets describe "$GCP_KEY_SECRET" >/dev/null 2>&1; then
  gcloud secrets create "$GCP_KEY_SECRET" --replication-policy=automatic
fi
gcloud secrets versions add "$GCP_KEY_SECRET" --data-file="$LOCAL_KEY_FILE"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" \
  --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding "$GCP_KEY_SECRET" \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role=roles/secretmanager.secretAccessor

# Read back the API server's URL; Used Claude Opus 5.5 for help with formatting for this section
API_SERVER_URL=$(gcloud run services describe "$API_SERVICE" \
  --region "$REGION" --format="value(urls[0])" 2>/dev/null || true)
if [ -z "$API_SERVER_URL" ]; then
  echo "Note: '$API_SERVICE' not found; API_SERVICE_URL left empty."
fi

# Deploy the Streamlit service
gcloud run deploy "$WEBAPP_SERVICE" \
  --source "$SCRIPT_DIR/streamlit" \
  --region "$REGION" \
  --port="$WEBAPP_PORT" \
  --allow-unauthenticated \
  --memory=1Gi \
  --env-vars-file="$ENV_FILE" \
  --set-secrets="$SECRET_MOUNT_PATH=$GCP_KEY_SECRET:latest"

# Load service account key
gcloud run services update "$WEBAPP_SERVICE" \
  --region "$REGION" \
  --update-env-vars=GCP_SERVICE_ACCOUNT_KEY="$SECRET_MOUNT_PATH",API_SERVICE_URL="$API_SERVER_URL"

WEBAPP_URL=$(gcloud run services describe "$WEBAPP_SERVICE" \
  --region "$REGION" --format="value(urls[0])")

echo
echo "Done."
echo "  Dashboard: $WEBAPP_URL"
