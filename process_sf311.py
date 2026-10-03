"""
Part E - Parse, clean and store SF 311 data into GCP.

Reads a raw 311 file that main.py saved in the bucket (/ingest/sf311),
cleans it, and stores the cleaned version under processed/ in the same bucket.

Run locally:
    fastapi dev process_sf311.py --port=8001
Then open http://127.0.0.1:8001/docs
"""
import json
import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from google.cloud import storage
from google.oauth2 import service_account
from pydantic import BaseModel

load_dotenv()  # Load environment variables from .env file

service_account_key = os.getenv("GCP_SERVICE_ACCOUNT_KEY")
project_id = os.getenv("GCP_PROJECT_ID")
bucket_name = os.getenv("GCS_BUCKET_NAME")   # same bucket variable main.py uses


# Google Cloud Storage

def retrieve_data_from_gcs(service_account_key, project_id, bucket_name, file_name):
    """Download a .ndjson file (one JSON record per line) and return a list of records."""
    credentials = service_account.Credentials.from_service_account_file(service_account_key)
    client = storage.Client(project=project_id, credentials=credentials)
    bucket = client.bucket(bucket_name)
    file = bucket.blob(file_name)
    if not file.exists():
        raise HTTPException(status_code=404, detail=f"{file_name} not found in {bucket_name}")
    data = file.download_as_bytes()

    records = []
    for line in data.decode("utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def store_to_gcs(service_account_key, project_id, bucket_name, file_name, data):
    """Upload a list of records as a .ndjson file (one JSON record per line)."""
    credentials = service_account.Credentials.from_service_account_file(service_account_key)
    client = storage.Client(project=project_id, credentials=credentials)
    bucket = client.bucket(bucket_name)
    file = bucket.blob(file_name)
    lines = [json.dumps(record) for record in data]
    file.upload_from_string("\n".join(lines) + "\n")
    return f"gs://{bucket_name}/{file_name}"


# Cleaning

def get_exclude_reason(status, notes, resolution_hours):
    """Why a record should NOT be used for the response-time analysis (None = use it)."""
    notes = (notes or "").lower()
    if status != "Closed" or resolution_hours is None:
        return "open"                  # not closed yet, so no resolution time
    if resolution_hours < 0:
        return "negative_duration"     # closed before it was opened (bad data)
    if "no work needed" in notes:
        return "no_work_needed"        # closed without any work being done
    if notes.startswith("unable_to_locate"):
        return "unable_to_locate"      # crew could not find the issue
    if "informational" in notes:
        return "informational"         # report is informational only (e.g. noise)
    return None


def clean_sf311_record(raw):
    """Clean one raw 311 record. Returns None if it has no location."""
    if not raw.get("lat") or not raw.get("long"):
        return None
    lat = float(raw["lat"])
    lon = float(raw["long"])
    if lat == 0 or lon == 0:
        return None

    requested_at = datetime.fromisoformat(raw["requested_datetime"])
    closed_at = None
    resolution_hours = None
    if raw.get("closed_date"):
        closed_at = datetime.fromisoformat(raw["closed_date"])
        resolution_hours = round((closed_at - requested_at).total_seconds() / 3600, 2)

    exclude_reason = get_exclude_reason(
        raw.get("status_description"), raw.get("status_notes"), resolution_hours
    )

    return {
        "service_request_id": raw.get("service_request_id"),
        "requested_at": requested_at.isoformat(),
        "closed_at": closed_at.isoformat() if closed_at else None,
        "status": raw.get("status_description"),
        "status_notes": raw.get("status_notes"),
        "service_name": raw.get("service_name"),
        "service_subtype": raw.get("service_subtype"),
        "agency_responsible": raw.get("agency_responsible"),
        "source": raw.get("source"),
        "lat": lat,
        "lon": lon,
        "analysis_neighborhood": raw.get("analysis_neighborhood"),
        "requested_date": requested_at.date().isoformat(),
        "resolution_hours": resolution_hours,
        "exclude_reason": exclude_reason,
        "valid_for_analysis": exclude_reason is None,
    }


def clean_sf311_records(raw_records):
    clean = []
    for raw in raw_records:
        record = clean_sf311_record(raw)
        if record is not None:
            clean.append(record)
    return clean


# API

class RawFile(BaseModel):
    # Path of a raw file from /ingest/sf311's "files" list, e.g.
    # raw/sf311/requested_2026-09-01_to_2026-09-02/run_20261003T175316Z/part-00001.ndjson
    file_name: str


class ProcessResponse(BaseModel):
    input_count: int
    output_count: int
    valid_for_analysis: int
    gcs_path: str


app = FastAPI(title="311 Income Response - Part E: Parse and Store")


@app.post("/process/sf311", response_model=ProcessResponse)
def process_sf311(request: RawFile):
    # Accept either "raw/sf311/..." or the full "gs://bucket/raw/sf311/..." path
    file_name = request.file_name.replace(f"gs://{bucket_name}/", "")
    if not file_name.startswith("raw/"):
        raise HTTPException(status_code=400, detail="file_name should start with raw/")

    raw_data = retrieve_data_from_gcs(service_account_key, project_id, bucket_name, file_name)
    clean_data = clean_sf311_records(raw_data)

    processed_file_name = file_name.replace("raw/", "processed/", 1)
    gcs_path = store_to_gcs(service_account_key, project_id, bucket_name,
                            processed_file_name, clean_data)

    valid = 0
    for record in clean_data:
        if record["valid_for_analysis"]:
            valid += 1

    return {"input_count": len(raw_data), "output_count": len(clean_data),
            "valid_for_analysis": valid, "gcs_path": gcs_path}
