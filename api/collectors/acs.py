"""Download and clean Census ACS data."""


import json
from datetime import date
from fastapi import HTTPException

from . import helper
import config
from data_types import ACSTract, FetchData, StoreData
from storage import upload_to_gcs

ACS_URL = "https://api.census.gov/data/{year}/acs/acs5"
ACS_YEAR = 2024

STATE_FIPS = "06"

COUNTY_FIPS = "075"


def file_names(fetch_date, year):
    """Return the raw and cleaned file paths in the bucket for one ACS year."""
    folder = f"{config.raw_prefix}/acs/{fetch_date}"
    return [f"{folder}/acs_raw_{year}.json", f"{folder}/acs_{year}.csv"]


def fetch_acs_data(year: int = ACS_YEAR):
    """Download raw Census data and save it to GCS. """
    bucket = helper.configured_bucket()
    params = {
        "get": "NAME,B19013_001E,B01003_001E",
        "for": "tract:*",
        "in": f"state:{STATE_FIPS} county:{COUNTY_FIPS}",
        "key": config.census_api_key,
    }
    response = helper.fetch_response(ACS_URL.format(year=year), params=params)
    try:
        response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Census did not send JSON back, check CENSUS_API_KEY")
    
    fetched_date = date.today()
    raw_name =file_names(fetched_date, year)[0]
    gcs_path = upload_to_gcs(raw_name, response.content, "application/json", bucket)
    return FetchData(source="acs", fetched_date=fetched_date, raw_data_type="application/json", gcs_path=gcs_path, year=year)


def parse_acs_data(year: int = ACS_YEAR, fetch_date: date | None = None):
    """ Clean the raw Census file and save the CSV. Missing estimates are saved as blank."""
    if fetch_date is None:
        fetch_date = date.today()
    bucket = helper.configured_bucket()
    raw_name, file_name = file_names(fetch_date, year)
    raw_data = helper.read_raw(raw_name, bucket)
    try:
        table = json.loads(raw_data)
    except ValueError:
        raise HTTPException(status_code=422, detail="Not valid JSON")
    columns = table[0]
    records = []
    for row in table[1:]:
        tract = dict(zip(columns, row))
        income = int(tract["B19013_001E"])
        population = int(tract["B01003_001E"])
        records.append({
            "geoid": tract["state"] + tract["county"] + tract["tract"],
            "tract_name": tract["NAME"],
            "median_household_income": income if income >= 0 else None,
            "total_population": population if population >= 0 else None,
            "acs_year": year,
        })
    clean_df, skipped = helper.clean(records, ACSTract)
    clean_df["median_household_income"] = clean_df["median_household_income"].astype("Int64")
    clean_df["total_population"] = clean_df["total_population"].astype("Int64")
    gcs_path = upload_to_gcs(file_name, clean_df.to_csv(index=False), "text/csv", bucket)
    return StoreData(rows_saved=len(clean_df), rows_skipped=skipped, gcs_path=gcs_path)
