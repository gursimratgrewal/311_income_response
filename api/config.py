import os
from dotenv import load_dotenv

load_dotenv()

service_account_key = os.getenv("GCP_SERVICE_ACCOUNT_KEY")
project_id = os.getenv("GCP_PROJECT_ID")
bucket_name = os.getenv("GCP_BUCKET_NAME")
raw_prefix = os.getenv("RAW_PREFIX", "raw")
HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "120"))
census_api_key = os.getenv("CENSUS_API_KEY")
