"""Download and clean Open-Meteo weather data."""

import json
from datetime import date
from fastapi import HTTPException

from . import helper
import config
from data_types import FetchData, StoreData, WeatherHour
from storage import upload_to_gcs

WEATHER_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
SF_LAT = 37.7749
SF_LNG = -122.4194
WEATHER_VARS = ["temperature_2m", "precipitation", "rain", "weather_code", "wind_speed_10m"]


def file_names(fetch_date, start_date, end_date):
    """Return the raw and cleaned file paths in the bucket for one date range."""
    folder = f"{config.raw_prefix}/weather/{fetch_date}"
    period = f"{start_date}_to_{end_date}"
    return [f"{folder}/weather_raw_{period}.json", f"{folder}/weather_{period}.csv"]


def fetch_weather_data(start_date: date | None = None, end_date: date | None = None):
    """Download raw hourly weather from Open-Meteo and save it to GCS."""
    bucket = helper.configured_bucket()
    fetched_date = date.today()
    start_date, end_date = helper.resolve_dates(start_date, end_date, fetched_date)
    params = {
        "latitude": SF_LAT,
        "longitude": SF_LNG,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "hourly": ",".join(WEATHER_VARS),
        "timezone": "America/Los_Angeles",
    }
    response = helper.fetch_response(WEATHER_URL, params=params)
    raw_name = file_names(fetched_date, start_date, end_date)[0]
    gcs_path = upload_to_gcs(raw_name, response.content, "application/json", bucket)
    return FetchData(source="weather", fetched_date=fetched_date, raw_data_type="application/json", gcs_path=gcs_path, start_date=start_date, end_date=end_date)


def parse_weather_data(start_date: date | None = None, end_date: date | None = None, fetch_date: date | None = None):
    """Clean the raw weather file into one row per hour and save the CSV."""
    if fetch_date is None:
        fetch_date = date.today()
    bucket = helper.configured_bucket()
    start_date, end_date = helper.resolve_dates(start_date, end_date, fetch_date)
    raw_name, file_name = file_names(fetch_date, start_date, end_date)
    raw_data = helper.read_raw(raw_name, bucket)
    try:
        table = json.loads(raw_data)
    except ValueError:
        raise HTTPException(status_code=422, detail="Saved weather file is not valid JSON") from None
    hourly = table["hourly"]
    records = []
    for i in range(len(hourly["time"])):
        record = {"time": hourly["time"][i], "lat": SF_LAT, "lng": SF_LNG}
        for var in WEATHER_VARS:
            record[var] = hourly[var][i]
        records.append(record)
    clean_df, skipped = helper.clean(records, WeatherHour)
    clean_df["weather_code"] = clean_df["weather_code"].astype("Int64")
    
    gcs_path = upload_to_gcs(file_name, clean_df.to_csv(index=False), "text/csv", bucket)
    return StoreData(rows_saved=len(clean_df), rows_skipped=skipped, gcs_path=gcs_path)
