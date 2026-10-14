"""Download and clean Census ACS data."""


import os, requests
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from datetime import date
from data_types import ACSTract, FetchData


load_dotenv()

census_api_key = os.getenv("CENSUS_API_KEY")
HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "120"))

ACS_URL = "https://api.census.gov/data/{year}/acs/acs5"
ACS_YEAR = 2024
STATE_FIPS = "06"
COUNTY_FIPS = "075"

app = FastAPI()

def clean(records, data_type):
    """Checks each row against the data type and counts the ones that fail."""
    rows = []
    skipped = 0
    for record in records:
        try:
            rows.append(data_type(**record).model_dump())
        except ValidationError:
            skipped += 1
    return pd.DataFrame(rows, columns=list(data_type.model_fields.keys())), skipped


@app.get("/")
def root():
    """Returns a welcome message from the api sources."""
    return {"message": "Welcome to the Census Data Fetch API"}


@app.get("/fetch/acs", response_model=FetchData)
def fetch_acs_data(year: int = ACS_YEAR):
    """Gets the median household income and population for every SF census tract. Missing estimates are saved as blank."""

    params = {
        "get": "NAME,B19013_001E,B01003_001E",
        "for": "tract:*",
        "in": f"state:{STATE_FIPS} county:{COUNTY_FIPS}",
        "key": census_api_key,
    }
    response = requests.get(ACS_URL.format(year=year), params=params, timeout=HTTP_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch data from source")

    try:
        table = response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Census did not send JSON back, check CENSUS_API_KEY")


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
    clean_df, skipped = clean(records, ACSTract)
    clean_df["median_household_income"] = clean_df["median_household_income"].astype("Int64")
    clean_df["total_population"] = clean_df["total_population"].astype("Int64")


    return FetchData(
        source="acs",
        fetched_date=date.today(),
        raw_data=response.content,
        raw_data_type="application/json",
        data=clean_df.to_csv(index=False),
        rows_count=len(clean_df),
        rows_skipped=skipped,
        year=year)
