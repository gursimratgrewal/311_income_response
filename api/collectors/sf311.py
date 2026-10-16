"""Download and clean SF 311 cases files."""

import io
import pandas as pd
from datetime import date
from pydantic import ValidationError

from . import helper
import config
from data_types import FetchData, SF311Case, StoreData
from storage import upload_to_gcs

FILE_URL = "https://data.sfgov.org/resource/vw6y-z8j6.csv"

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


def file_names(fetch_date, start_date, end_date):
    "Building file names"
    folder = f"{config.raw_prefix}/sf311/{fetch_date}"
    period = f"{start_date}_to_{end_date}"
    return [f"{folder}/sf311_raw_{period}.csv", f"{folder}/sf311_{period}.csv"]


def fetch_sf311_data(start_date: date | None = None, end_date: date | None = None):
    "Download the raw 311 cases and save them to GCS"
    bucket = helper.configured_bucket()
    fetched_date = date.today()
    start_date, end_date = helper.resolve_dates(start_date, end_date, fetched_date)
    params = {
        "$where": f"requested_datetime between '{start_date}T00:00:00' and '{end_date}T23:59:59'",
        "$limit": 100000,
    }
    response = helper.fetch_response(FILE_URL, params=params)
    raw_name = file_names(fetched_date, start_date, end_date)[0]
    gcs_path = upload_to_gcs(raw_name, response.content, "text/csv", bucket)
    return FetchData(source="sf311", fetched_date=fetched_date, raw_data_type="text/csv", gcs_path=gcs_path, start_date=start_date, end_date=end_date)


def parse_sf311_data(start_date: date | None = None, end_date: date | None = None, fetch_date: date | None = None):
    """Cleans SF 311 cases opened between start_date and end_date as a CSV file"""
    bucket = helper.configured_bucket()
    if fetch_date is None:
        fetch_date = date.today()
    start_date, end_date = helper.resolve_dates(start_date, end_date, fetch_date)
    raw_name, file_name = file_names(fetch_date, start_date, end_date)
    raw_data = helper.read_raw(raw_name, bucket)
    df = pd.read_csv(io.BytesIO(raw_data), usecols=list(Column_names.keys()), dtype=str)
    clean_df, skipped = clean(df)
    gcs_path = upload_to_gcs(file_name, clean_df.to_csv(index=False), "text/csv", bucket)
    return StoreData(rows_saved=len(clean_df), rows_skipped=skipped, gcs_path=gcs_path)
