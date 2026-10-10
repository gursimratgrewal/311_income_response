import os
import pandas as pd
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from google.cloud import storage
from google.oauth2 import service_account

from pydantic import ValidationError
from data_types import FetchData, SF311Case

load_dotenv()

service_account_key = os.getenv("GCP_SERVICE_ACCOUNT_KEY")
project_id = os.getenv("GCP_PROJECT_ID")
bucket_name = os.getenv("GCS_BUCKET_NAME")
raw_prefix = os.getenv("RAW_PREFIX", "raw")

FILE_URL= "https://data.sfgov.org/api/views/vw6y-z8j6/rows.csv?accessType=DOWNLOAD"
size = 500000

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
GCP_SERVICE_ACCOUNT_KEY = os.getenv("GCP_SERVICE_ACCOUNT_KEY")
RAW_PREFIX = os.getenv("RAW_PREFIX", "raw")
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
    if service_account_key:
        cred = service_account.Credentials.from_service_account_file(service_account_key)
        client = storage.Client(credentials=cred, project=project_id)
    else:
        client = storage.Client(project=project_id)
    return client.bucket(bucket_name)

def clean(chunk):
    chunk = chunk.rename(columns=Column_names)
    for date_col in Dates:
        chunk[date_col] = pd.to_datetime(chunk[date_col], errors='coerce', format="mixed")
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
    return {"message": "Welcome to the SF311 Data Fetch API"}

@app.get("/fetch", response_model=FetchData)
def fetch_sf311_data(max_rows: int | None=None):
    if not bucket_name:
        raise HTTPException(status_code=500, detail="Bucket name not configured")
    response = requests.get(FILE_URL, stream=True, timeout=HTTP_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch data from source")

    response.raw.decode_content = True
    reader = pd.read_csv(response.raw, usecols=list(Column_names.keys()), dtype=str,
                         chunksize=size, nrows=max_rows)
    #data = io.BytesIO(response.content)
    

    bucket = get_bucket()
    folder = f"{raw_prefix}/sf311"
    saved = 0
    skipped = 0
    for i, chunk in enumerate(reader):
        clean_df, chunk_skipped = clean(chunk)
        file = bucket.blob(f"{folder}/sf311_part_{i:03d}.csv")
        file.upload_from_string(clean_df.to_csv(index=False), content_type='text/csv')
        saved += len(clean_df)
        skipped += chunk_skipped

    return {"rows_saved": saved, "rows_skipped": skipped, "gcs_path": f"gs://{bucket.name}/{folder}"}