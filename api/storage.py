"""gcs connection, upload and download"""

import config
from google.cloud import storage
from google.oauth2 import service_account

def get_bucket():
    """Returns the GCS bucket."""
    if config.service_account_key:
        cred = service_account.Credentials.from_service_account_file(config.service_account_key)
        client = storage.Client(credentials=cred, project=config.project_id)
    else:
        client = storage.Client(project=config.project_id)
    return client.bucket(config.bucket_name)


def upload_to_gcs(file_name, data, content_type, bucket):
    """Upload a file to the bucket"""
    bucket.blob(file_name).upload_from_string(data, content_type=content_type)
    return f"gs://{bucket.name}/{file_name}"


def retrieve_data_from_gcs(file_name, bucket):
    """Download a file from the bucket"""
    return bucket.blob(file_name).download_as_bytes()
