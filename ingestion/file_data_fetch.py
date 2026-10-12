""" FASTAPI that downloads the SF 311 Cases data CSV file and it stores in the GCS."""

import os
import io
import pandas as pd
import requests
from dotenv import load_dotenv
from datetime import date, timedelta
from fastapi import FastAPI, HTTPException
from google.cloud import storage
from google.oauth2 import service_account

from pydantic import ValidationError
from data_types import FetchData, SF311Case

load_dotenv()

service_account_key = os.getenv("GCP_SERVICE_ACCOUNT_KEY")
project_id = os.getenv("GCP_PROJECT_ID")
bucket_name = os.getenv("GCP_BUCKET_NAME")
raw_prefix = os.getenv("RAW_PREFIX", "raw")

FILE_URL = "https://data.sfgov.org/resource/vw6y-z8j6.csv"


HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "120"))

Column_names = {
    "service_request_id": "service_request_id",
    "requested_datetime": "created_date",
    "closed_date": "closed_date",
    "updated_datetime": "updated_date",
    "status_description": "status",
    "agency_responsible": "responsible_agency",
    "service_name": "service_category",
    "service_subtype": "request_type",
    "supervisor_district": "supervisor_dist",
    "analysis_neighborhood": "neighborhood",
    "police_district": "police_dist",
    "lat": "lat",
    "long": "lng",
    "source": "source",
}
Dates = ["created_date", "closed_date", "updated_date"]
         
app = FastAPI()

def get_bucket():
    """Return GCS bucket."""
    if service_account_key:
        cred = service_account.Credentials.from_service_account_file(service_account_key)
        client = storage.Client(credentials=cred, project=project_id)
    else:
        client = storage.Client(project=project_id)
    return client.bucket(bucket_name)

def clean(chunk):
    """Rename columns,validating each rows and coverting dates."""
    chunk = chunk.rename(columns=Column_names)
    for date_col in Dates:
        chunk[date_col] = pd.to_datetime(chunk[date_col], errors='coerce', format="ISO8601")
    non_empty = chunk.notna()
    chunk = chunk.astype(object).where(non_empty, None)

    rows = []
    skipped = 0
    for record in chunk.to_dict('records'):
        try:
            rows.append(SF311Case(**record).model_dump())
        except ValidationError:
            skipped += 1
    return pd.DataFrame(rows,columns=list(SF311Case.model_fields.keys())), skipped

@app.get("/")
def root():
    """Returning a welcome message."""
    return {"message": "Welcome to the SF311 Data Fetch API"}

@app.get("/fetch", response_model=FetchData)
def fetch_sf311_data(start_date: date | None = None, end_date: date | None = None):
    """Download SF 311 cases opened between start_date and end_date as a CSV file,
    """
    if end_date is None:
        end_date = date.today() - timedelta(days=1)  
    if start_date is None:
        start_date = end_date - timedelta(days=1)   
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    if not bucket_name:
        raise HTTPException(status_code=500, detail="Bucket name is not configured")

    params = {
        "$where": f"requested_datetime between '{start_date}T00:00:00' and '{end_date}T23:59:59'",
        "$limit": 100000,
    }
    response = requests.get(FILE_URL, params=params, timeout=HTTP_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch data from source")

    bucket = get_bucket()
    folder = f"{raw_prefix}/sf311/{date.today()}"

    raw_name = f"{folder}/sf311_raw_{start_date}_to_{end_date}.csv"
    bucket.blob(raw_name).upload_from_string(response.content, content_type="text/csv")

    df = pd.read_csv(io.BytesIO(response.content), usecols=list(Column_names.keys()), dtype=str)
    clean_df, skipped = clean(df)

    file_name = f"{folder}/sf311_{start_date}_to_{end_date}.csv"
    bucket.blob(file_name).upload_from_string(clean_df.to_csv(index=False), content_type="text/csv")

    return {"rows_saved": len(clean_df), "rows_skipped": skipped,
            "gcs_path": f"gs://{bucket.name}/{file_name}"}