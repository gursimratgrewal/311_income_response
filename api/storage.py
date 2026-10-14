"""Read and store data in GCS using the original collector file layout."""

import io, os
import pandas as pd
from dotenv import load_dotenv
from fastapi import HTTPException
from google.cloud import storage
from google.oauth2 import service_account
from data_types import FetchData, StoreData

load_dotenv()

service_account_key = os.getenv("GCP_SERVICE_ACCOUNT_KEY")
project_id = os.getenv("GCP_PROJECT_ID")
bucket_name = os.getenv("GCP_BUCKET_NAME")
raw_prefix = os.getenv("RAW_PREFIX", "raw")


def get_bucket():
    """Returns the GCS bucket."""
    if service_account_key:
        cred = service_account.Credentials.from_service_account_file(service_account_key)
        client = storage.Client(credentials=cred, project=project_id)
    else:
        client = storage.Client(project=project_id)
    return client.bucket(bucket_name)


def upload_to_gcs(file_name, data, content_type, bucket):
    """Upload raw data"""
    bucket.blob(file_name).upload_from_string(data, content_type=content_type)
    return f"gs://{bucket.name}/{file_name}"


def save_data(data: FetchData) -> StoreData:
    """Save the raw file and cleaned CSV to gcs"""
    if not bucket_name:
        raise HTTPException(status_code=500, detail="Bucket name is not configured")

    folder = f"{raw_prefix}/{data.source}/{data.fetched_date}"

    if data.source == "acs":
        if data.year is None:
            raise HTTPException(status_code=400, detail="year is required for ACS data")
        raw_name = f"{folder}/acs_raw_{data.year}.json"
        file_name = f"{folder}/acs_{data.year}.csv"

    elif data.source in ("weather", "sf311"):
        if data.start_date is None or data.end_date is None:
            raise HTTPException(status_code=400, detail="start_date and end_date are required")
        if data.start_date > data.end_date:
            raise HTTPException(status_code=400, detail="start_date must be before end_date")
        
        period = f"{data.start_date}_to_{data.end_date}"
        if data.source == "weather":
            extension = "json"
        else:
            extension = "csv"
        raw_name = f"{folder}/{data.source}_raw_{period}.{extension}"
        file_name = f"{folder}/{data.source}_{period}.csv"

    elif data.source == "neighborhoods":
        raw_name = f"{folder}/tract_neighborhoods_raw.csv"
        file_name = f"{folder}/tract_neighborhoods.csv"

    else:
        raise HTTPException(status_code=400, detail="Unknown data source")

    bucket = get_bucket()
    upload_to_gcs(raw_name, data.raw_data, content_type=data.raw_data_type, bucket=bucket)
    gcs_path = upload_to_gcs(file_name, data.data, content_type="text/csv", bucket=bucket)

    return StoreData(
        rows_saved=data.rows_count,
        rows_skipped=data.rows_skipped,
        gcs_path=gcs_path)


def retrieve_data_from_gcs(file_name):
    """Download a file from the bucket and return it as a DataFrame."""
    data = get_bucket().blob(file_name).download_as_bytes()
    return pd.read_csv(io.BytesIO(data), dtype={"geoid": str})


def store_to_gcs(file_name, df):
    """Upload a DataFrame to the bucket as a CSV file."""
    upload_to_gcs(file_name, df.to_csv(index=False), content_type="text/csv", bucket=get_bucket())

