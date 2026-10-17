"""gcs connection, upload and download"""

from google.cloud import storage
from google.oauth2 import service_account

from user_definition import project_id, bucket_name, service_account_key


def get_bucket():
    """Returns the GCS bucket."""
    if service_account_key:
        cred = service_account.Credentials.from_service_account_file(service_account_key)
        client = storage.Client(credentials=cred, project=project_id)
    else:
        client = storage.Client(project=project_id)
    return client.bucket(bucket_name)


def upload_to_gcs(file_name, data, content_type, bucket):
    """Upload a file to the bucket"""
    bucket.blob(file_name).upload_from_string(data, content_type=content_type)
    return f"gs://{bucket.name}/{file_name}"


def retrieve_data_from_gcs(file_name, bucket):
    """Download a file from the bucket"""
    return bucket.blob(file_name).download_as_bytes()
