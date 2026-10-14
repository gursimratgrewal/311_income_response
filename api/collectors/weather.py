"""Download and clean Open-Meteo weather data."""


import os, requests
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from datetime import date, timedelta
from data_types import WeatherHour, FetchData


load_dotenv()

HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "120"))

WEATHER_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
SF_LAT = 37.7749            
SF_LNG = -122.4194
WEATHER_VARS = ["temperature_2m", "precipitation", "rain", "weather_code", "wind_speed_10m"]

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
    return {"message": "Welcome to the Weather Data Fetch API"}


@app.get("/fetch/weather", response_model=FetchData)
def fetch_weather_data(start_date: date | None = None, end_date: date | None = None):
    """Gets hourly SF weather between start_date and end_date from Open-Meteo. Default is the last 2 days ending yesterday."""
    if end_date is None:
        end_date = date.today() - timedelta(days=1)
    if start_date is None:
        start_date = end_date - timedelta(days=1)
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

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


    hourly = response.json()["hourly"]
    records = []
    for i in range(len(hourly["time"])):
        record = {"time": hourly["time"][i], "lat": SF_LAT, "lng": SF_LNG}
        for var in WEATHER_VARS:
            record[var] = hourly[var][i]
        records.append(record)
    clean_df, skipped = clean(records, WeatherHour)
    clean_df["weather_code"] = clean_df["weather_code"].astype("Int64")


    return FetchData(
        source="weather",
        fetched_date=date.today(),
        raw_data=response.content,
        data=clean_df.to_csv(index=False),
        raw_data_type="application/json",
        rows_count=len(clean_df),
        rows_skipped=skipped,
        start_date=start_date,
        end_date=end_date)
