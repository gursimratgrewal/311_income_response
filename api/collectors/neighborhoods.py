"""Download and clean tract-neighborhood files."""

import io
import pandas as pd
from datetime import date
from pydantic import ValidationError

from . import helper
import config
from data_types import FetchData, StoreData, TractNeighborhood
from storage import upload_to_gcs

Neighborhood_file_path = "https://data.sfgov.org/api/views/sevw-6tgi/rows.csv?accessType=DOWNLOAD"

Neighborhood_Column_names = { "geoid": "geoid",
    "name": "tract_name",
    "neighborhoods_analysis_boundaries": "neighborhood",
    "sup_dist_2022": "supervisor_dist",
}


def file_names(fetch_date):
    folder = f"{config.raw_prefix}/neighborhoods/{fetch_date}"
    return f"{folder}/tract_neighborhoods_raw.csv", f"{folder}/tract_neighborhoods.csv"


def fetch_neighborhoods():
    bucket = helper.configured_bucket()
    response = helper.fetch_response(Neighborhood_file_path)
    fetched_date = date.today()
    raw_name = file_names(fetched_date)[0]
    gcs_path = upload_to_gcs(raw_name, response.content, "text/csv", bucket)
    return FetchData(source="neighborhoods", fetched_date=fetched_date, raw_data_type="text/csv", gcs_path=gcs_path)


def parse_neighborhoods(fetch_date: date | None = None):
    """Download the SF census tract to neighborhood CSV file (file-based source)"""
    bucket = helper.configured_bucket()
    if fetch_date is None:
        fetch_date = date.today()
    raw_name, file_name = file_names(fetch_date)
    raw_data = helper.read_raw(raw_name, bucket)
    df = pd.read_csv(io.BytesIO(raw_data), usecols=list(Neighborhood_Column_names.keys()), dtype=str)
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
    gcs_path = upload_to_gcs(file_name, clean_df.to_csv(index=False), "text/csv", bucket)
    return StoreData(rows_saved=len(clean_df), rows_skipped=skipped, gcs_path=gcs_path)
