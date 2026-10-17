CONFIG_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ENV_FILE="$CONFIG_DIR/.env"
source "$ENV_FILE"
PROJECT_ID="${GCP_PROJECT_ID}"
LOCAL_KEY_FILE="${GCP_SERVICE_ACCOUNT_KEY}"

REGION="us-west1"
API_PORT="8000"
WEBAPP_PORT="8501"

GCP_KEY_SECRET=311-gcp-key
SECRET_MOUNT_PATH=/run/secrets/gcp_key

API_SERVICE=sf311-api-server
FETCH_SERVICE=sf311-fetch
PARSE_SERVICE=sf311-parse
WEBAPP_SERVICE=sf311-webapp

SOURCES="acs weather sf311 neighborhoods"

FETCH_SCHEDULER_JOB=sf311-fetch-trigger
PARSE_SCHEDULER_JOB=sf311-parse-trigger
PROCESS_SCHEDULER_JOB=sf311-process-trigger
FETCH_SCHEDULE="0 1 * * *"
PARSE_SCHEDULE="0 2 * * *"
PROCESS_SCHEDULE="0 3 * * *"

FETCH_PATH=/fetch
PARSE_PATH=/parse
PROCESS_PATH=/process

for _sf311_var in PROJECT_ID REGION ENV_FILE LOCAL_KEY_FILE API_PORT \
                WEBAPP_PORT; do
  if [ -z "${!_sf311_var}" ]; then
    echo "ERROR: $_sf311_var is empty - fill in TODOs in config.sh" \
         "before running this script." >&2
    exit 1
  fi
done
unset _sf311_var

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: ENV_FILE '$ENV_FILE' does not exist." >&2
  exit 1
fi
if [ ! -f "$LOCAL_KEY_FILE" ]; then
  echo "ERROR: LOCAL_KEY_FILE '$LOCAL_KEY_FILE' does not exist." >&2
  exit 1
fi

