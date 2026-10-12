""" FASTAPI that downloads the SF 311 Cases data CSV file and it stores in the GCS."""

import os 
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

FILE_URL= "https://data.sfgov.org/api/views/vw6y-z8j6/rows.csv?accessType=DOWNLOAD"
size = 500000

HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "120"))

Column_names = {
   "CaseID": "service_request_id",
    "Opened": "created_date",
    "Closed": "closed_date",
    "Updated": "updated_date",
    "Status": "status",
    "Responsible Agency": "responsible_agency",
    "Category": "service_category",
    "Request Type": "request_type",
    "Supervisor District": "supervisor_dist",
    "Analysis Neighborhood": "neighborhood",
    "Police District": "police_dist",
    "Latitude": "lat",
    "Longitude": "lng",
    "Source": "source",
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
        chunk[date_col] = pd.to_datetime(chunk[date_col], errors='coerce', format="%m/%d/%Y %I:%M:%S %p")
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
    """Download the SF 311 data CSV and keep cases opened between start date and end date and upload to GCS."""
    if end_date is None:
        end_date = date.today() - timedelta(days=1)
    if start_date is None:
        start_date = end_date - timedelta(days=29)
    if not bucket_name:
        raise HTTPException(status_code=500, detail="Bucket name not configured")
    response = requests.get(FILE_URL, stream=True, timeout=HTTP_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch data from source")

   
    #data = io.BytesIO(response.content)
    
    response.raw.decode_content = True
    bucket = get_bucket()
    folder = f"{raw_prefix}/sf311/{date.today()}"
    raw_file = bucket.blob(f"{folder}/sf311_raw.csv", chunk_size=50 * 1024 * 1024)
    raw_file.upload_from_file(response.raw, content_type="text/csv")
    reader = pd.read_csv(raw_file.open("r"), usecols=list(Column_names.keys()), dtype=str,
                         chunksize=size)
    kept = []
    skipped = 0
    for chunk in reader:
        opened = pd.to_datetime(chunk["Opened"], errors="coerce", format="%m/%d/%Y %I:%M:%S %p").dt.date
        in_range = chunk[(opened >= start_date) & (opened <= end_date)]
        clean_df, chunk_skipped = clean(in_range)
        kept.append(clean_df)
        skipped += chunk_skipped

    all_rows = pd.concat(kept)
    file_name = f"{folder}/sf311_{start_date}_to_{end_date}.csv"
    file = bucket.blob(file_name)
    file.upload_from_string(all_rows.to_csv(index=False), content_type="text/csv")
       
    return {"rows_saved": len(all_rows), "rows_skipped": skipped,
            "gcs_path": f"gs://{bucket.name}/{file_name}"}