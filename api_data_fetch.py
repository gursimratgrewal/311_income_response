""" FASTAPI that gets Census ACS and Open-Meteo weather data from their APIs and stores it in the GCS."""

import os
import pandas as pd
import requests
from dotenv import load_dotenv
from datetime import date, timedelta
from fastapi import FastAPI, HTTPException
from google.cloud import storage
from google.oauth2 import service_account
from pydantic import ValidationError
from data_types import ACSTract, FetchData, WeatherHour

load_dotenv()

service_account_key = os.getenv("GCP_SERVICE_ACCOUNT_KEY")
project_id = os.getenv("GCP_PROJECT_ID")
bucket_name = os.getenv("GCP_BUCKET_NAME")
raw_prefix = os.getenv("RAW_PREFIX", "raw")
census_api_key = os.getenv("CENSUS_API_KEY")

HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "120"))

ACS_URL = "https://api.census.gov/data/{year}/acs/acs5"
ACS_YEAR = 2024             
STATE_FIPS = "06"           
COUNTY_FIPS = "075"         

WEATHER_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
SF_LAT = 37.7749            
SF_LNG = -122.4194
WEATHER_VARS = ["temperature_2m", "precipitation", "rain", "weather_code", "wind_speed_10m"]

app = FastAPI()

def get_bucket():
    """Returns the GCS bucket."""
    if service_account_key:
        cred = service_account.Credentials.from_service_account_file(service_account_key)
        client = storage.Client(credentials=cred, project=project_id)
    else:
        client = storage.Client(project=project_id)
    return client.bucket(bucket_name)

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
    return {"message": "Welcome to the Census and Weather Data Fetch API"}


@app.get("/fetch/acs", response_model=FetchData)
def fetch_acs_data(year: int = ACS_YEAR):
    """Gets the median household income and population for every SF census tract. Missing estimates are saved as blank."""
    if not bucket_name:
        raise HTTPException(status_code=500, detail="Bucket name is not configured")

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

    bucket = get_bucket()
    folder = f"{raw_prefix}/acs/{date.today()}"

    raw_name = f"{folder}/acs_raw_{year}.json"
    bucket.blob(raw_name).upload_from_string(response.content, content_type="application/json")

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

    file_name = f"{folder}/acs_{year}.csv"
    bucket.blob(file_name).upload_from_string(clean_df.to_csv(index=False), content_type="text/csv")

    return {"rows_saved": len(clean_df), "rows_skipped": skipped,
            "gcs_path": f"gs://{bucket.name}/{file_name}"}

@app.get("/fetch/weather", response_model=FetchData)
def fetch_weather_data(start_date: date | None = None, end_date: date | None = None):
    """Gets hourly SF weather between start_date and end_date from Open-Meteo. Default is the last 2 days ending yesterday."""
    if end_date is None:
        end_date = date.today() - timedelta(days=1)
    if start_date is None:
        start_date = end_date - timedelta(days=1)
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    if not bucket_name:
        raise HTTPException(status_code=500, detail="Bucket name is not configured")

    params = {
        "latitude": SF_LAT,
        "longitude": SF_LNG,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "hourly": ",".join(WEATHER_VARS),
        "timezone": "America/Los_Angeles",  
    }
    response = requests.get(WEATHER_URL, params=params, timeout=HTTP_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch data from source")

    bucket = get_bucket()
    folder = f"{raw_prefix}/weather/{date.today()}"

    raw_name = f"{folder}/weather_raw_{start_date}_to_{end_date}.json"
    bucket.blob(raw_name).upload_from_string(response.content, content_type="application/json")

    hourly = response.json()["hourly"]
    records = []
    for i in range(len(hourly["time"])):
        record = {"time": hourly["time"][i], "lat": SF_LAT, "lng": SF_LNG}
        for var in WEATHER_VARS:
            record[var] = hourly[var][i]
        records.append(record)
    clean_df, skipped = clean(records, WeatherHour)
    clean_df["weather_code"] = clean_df["weather_code"].astype("Int64")

    file_name = f"{folder}/weather_{start_date}_to_{end_date}.csv"
    bucket.blob(file_name).upload_from_string(clean_df.to_csv(index=False), content_type="text/csv")

    return {"rows_saved": len(clean_df), "rows_skipped": skipped,
            "gcs_path": f"gs://{bucket.name}/{file_name}"}
