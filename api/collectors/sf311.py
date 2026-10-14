"""Download and clean SF 311 cases and tract-neighborhood files."""


import os, io, requests
import pandas as pd
from dotenv import load_dotenv
from datetime import date, timedelta
from fastapi import HTTPException
from pydantic import ValidationError
from data_types import SF311Case, TractNeighborhood, FetchData


load_dotenv()

HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "120"))

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

Neighborhood_file_path = "https://data.sfgov.org/api/views/sevw-6tgi/rows.csv?accessType=DOWNLOAD"

Neighborhood_Column_names = { "geoid": "geoid",
    "name": "tract_name",
    "neighborhoods_analysis_boundaries": "neighborhood",
    "sup_dist_2022": "supervisor_dist",
}
         

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


def fetch_sf311_data(start_date: date | None = None, end_date: date | None = None):
    """Download SF 311 cases opened between start_date and end_date as a CSV file,
    """
    if end_date is None:
        end_date = date.today() - timedelta(days=1)  
    if start_date is None:
        start_date = end_date - timedelta(days=1)   
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    params = {
        "$where": f"requested_datetime between '{start_date}T00:00:00' and '{end_date}T23:59:59'",
        "$limit": 100000,
    }
    response = requests.get(FILE_URL, params=params, timeout=HTTP_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch data from source")


    df = pd.read_csv(io.BytesIO(response.content), usecols=list(Column_names.keys()), dtype=str)
    clean_df, skipped = clean(df)


    return FetchData(
        source="sf311",
        fetched_date=date.today(),
        raw_data=response.content,
        raw_data_type="text/csv",
        data=clean_df.to_csv(index=False),
        rows_count=len(clean_df),
        rows_skipped=skipped,
        start_date=start_date,
        end_date=end_date)

def fetch_neighborhoods():
    """Download the SF census tract to neighborhood CSV file (file-based source),
    """

    response = requests.get(Neighborhood_file_path, timeout=HTTP_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch neighborhood file")


    df = pd.read_csv(io.BytesIO(response.content), usecols=list(Neighborhood_Column_names.keys()), dtype=str)
    df = df.rename(columns=Neighborhood_Column_names)
    df = df.astype(object).where(df.notna(), None)

    rows = []
    skipped = 0
    for record in df.to_dict("records"):
        try:
            rows.append(TractNeighborhood(**record).model_dump())
        except ValidationError:
            skipped += 1
    clean_df = pd.DataFrame(rows, columns=list(TractNeighborhood.model_fields.keys()))


    return FetchData(
        source="neighborhoods",
        fetched_date=date.today(),
        raw_data=response.content,
        raw_data_type="text/csv",
        data=clean_df.to_csv(index=False),
        rows_count=len(clean_df),
        rows_skipped=skipped)
