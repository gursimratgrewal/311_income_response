# Streamlit dashboard settings
# GCP project ID
PROJECT_ID="data-acqusition-group-project"

#Region. Must match the other Cloud Run services / scheduler.
REGION="us-west1"

# Absolute path to the project .env 
ENV_FILE="/Users/erics359/USF_Classes/group_assignment/311_income_response/.env"

# Absolute path to service account JSON
LOCAL_KEY_FILE="/Users/erics359/.ssh/data-acqusition-group-project-53080a97e298.json"

WEBAPP_PORT="8501"

GCP_KEY_SECRET=sf311-gcp-key
SECRET_MOUNT_PATH=/run/secrets/gcp_key

# Taken from Claude after asking Opus 5.5 how to deconflict a
# running cloud api when trying to cloud run streamlit
WEBAPP_SERVICE=sf311-webapp
# If the API service is already deployed under this name, its URL is
# passed to the dashboard as API_SERVICE_URL
API_SERVICE=processing-api

# Validation
# Used Claude asking Opus 5.5 how to troubleshoot errors 
# when trying to cloud run streamlit
for _var in PROJECT_ID REGION ENV_FILE LOCAL_KEY_FILE WEBAPP_PORT; do
  if [ -z "${!_var}" ]; then
    echo "ERROR: $_var is empty - fill in TODOs in webapp_config.sh" >&2
    exit 1
  fi
done
unset _var

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: ENV_FILE '$ENV_FILE' does not exist." >&2
  exit 1
fi
if [ ! -f "$LOCAL_KEY_FILE" ]; then
  echo "ERROR: LOCAL_KEY_FILE '$LOCAL_KEY_FILE' does not exist." >&2
  exit 1
fi
