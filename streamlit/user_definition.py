import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
project_id = os.getenv('GCP_PROJECT_ID')
bucket_name = os.getenv('GCP_BUCKET_NAME')
service_account_file_path = os.getenv('GCP_SERVICE_ACCOUNT_KEY')
# Processing API (processing/process_sf311.py) with GET /summary and /data.
# Falls back to the deployed URL when API_SERVICE_URL is not set.
api_server_url = os.getenv('API_SERVICE_URL') or \
    'https://processing-api-992866704994.us-west1.run.app'
