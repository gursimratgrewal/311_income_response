#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/config.sh"

gcloud config set project "$PROJECT_ID"
gcloud config set run/region "$REGION"

gcloud services enable secretmanager.googleapis.com cloudscheduler.googleapis.com

if ! gcloud secrets describe "$GCP_KEY_SECRET" >/dev/null 2>&1; then
  gcloud secrets create "$GCP_KEY_SECRET" --replication-policy=automatic
fi

gcloud secrets versions add "$GCP_KEY_SECRET" --data-file="$LOCAL_KEY_FILE"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" \
  --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding "$GCP_KEY_SECRET" \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role=roles/secretmanager.secretAccessor

API_SERVICES="$API_SERVICE"
for SOURCE in $SOURCES; do
  API_SERVICES="$API_SERVICES $FETCH_SERVICE-$SOURCE $PARSE_SERVICE-$SOURCE"
done

for SERVICE in $API_SERVICES; do
  gcloud run deploy "$SERVICE" \
    --source "./api" \
    --region "$REGION" \
    --port="$API_PORT" \
    --allow-unauthenticated \
    --env-vars-file="$ENV_FILE" \
    --set-secrets="$SECRET_MOUNT_PATH=$GCP_KEY_SECRET:latest" \
    --memory="2Gi" \
    --cpu=2 \
    --timeout=3600

  gcloud run services update "$SERVICE" \
    --region "$REGION" \
    --update-env-vars=GCP_SERVICE_ACCOUNT_KEY="$SECRET_MOUNT_PATH"
done

API_SERVER_URL=$(gcloud run services describe "$API_SERVICE" \
  --region "$REGION" --format="value(urls[0])")
if [ -z "$API_SERVER_URL" ]; then
  API_SERVER_URL=$(gcloud run services describe "$API_SERVICE" \
    --region "$REGION" --format="value(status.url)")
fi
if [ -z "$API_SERVER_URL" ]; then
  echo "ERROR: could not resolve the URL for Cloud Run service" \
       "'$API_SERVICE' in $REGION." >&2
  exit 1
fi
echo "$API_SERVICE deployed at $API_SERVER_URL"

gcloud run deploy "$WEBAPP_SERVICE" \
  --source "./streamlit" \
  --region "$REGION" \
  --port="$WEBAPP_PORT" \
  --allow-unauthenticated \
  --env-vars-file="$ENV_FILE" \
  --set-secrets="$SECRET_MOUNT_PATH=$GCP_KEY_SECRET:latest"

gcloud run services update "$WEBAPP_SERVICE" \
  --region "$REGION" \
  --update-env-vars=GCP_SERVICE_ACCOUNT_KEY="$SECRET_MOUNT_PATH",API_SERVICE_URL="$API_SERVER_URL"

WEBAPP_URL=$(gcloud run services describe "$WEBAPP_SERVICE" \
  --region "$REGION" --format="value(urls[0])")
echo "$WEBAPP_SERVICE deployed at $WEBAPP_URL"


for SOURCE in $SOURCES; do
  for STAGE in fetch parse; do
    if [ "$STAGE" = "fetch" ]; then
      SERVICE="$FETCH_SERVICE-$SOURCE"
      SCHEDULER_JOB="$FETCH_SCHEDULER_JOB-$SOURCE"
      SCHEDULE="$FETCH_SCHEDULE"
      REQUEST_PATH="$FETCH_PATH/$SOURCE"
    else
      SERVICE="$PARSE_SERVICE-$SOURCE"
      SCHEDULER_JOB="$PARSE_SCHEDULER_JOB-$SOURCE"
      SCHEDULE="$PARSE_SCHEDULE"
      REQUEST_PATH="$PARSE_PATH/$SOURCE"
    fi

    SERVICE_URL=$(gcloud run services describe "$SERVICE" \
      --region "$REGION" --format="value(urls[0])")

    if gcloud scheduler jobs describe "$SCHEDULER_JOB" \
         --location="$REGION" >/dev/null 2>&1; then
      SCHEDULER_ACTION=update
    else
      SCHEDULER_ACTION=create
    fi

    gcloud scheduler jobs "$SCHEDULER_ACTION" http "$SCHEDULER_JOB" \
      --location="$REGION" \
      --schedule="$SCHEDULE" \
      --uri="$SERVICE_URL$REQUEST_PATH" \
      --http-method=GET \
      --attempt-deadline=1800s

    echo "Scheduler: $SCHEDULER_JOB ($SCHEDULE)"
  done
done

if gcloud scheduler jobs describe "$PROCESS_SCHEDULER_JOB" \
     --location="$REGION" >/dev/null 2>&1; then
  SCHEDULER_ACTION=update
else
  SCHEDULER_ACTION=create
fi

gcloud scheduler jobs "$SCHEDULER_ACTION" http "$PROCESS_SCHEDULER_JOB" \
  --location="$REGION" \
  --schedule="$PROCESS_SCHEDULE" \
  --uri="$API_SERVER_URL$PROCESS_PATH" \
  --http-method=POST \
  --attempt-deadline=1800s

echo
echo "Done."
echo "  API:       $API_SERVER_URL"
echo "  Dashboard: $WEBAPP_URL"
echo "  Scheduler: $PROCESS_SCHEDULER_JOB ($PROCESS_SCHEDULE)"
