"""Part C - clean and join the 311, Census, weather and neighborhood files, and store the result in GCS."""

import io, json
import pandas as pd
from datetime import date

from storage import upload_to_gcs
from user_definition import JOINED_PATH, SUMMARY_PATH
from collectors import helper, sf311, acs, weather, neighborhoods


def retrieve_data_from_gcs(file_name, bucket=None):
    """Download a file from the bucket and return it as a DataFrame."""
    if bucket is None:
        bucket = helper.configured_bucket()
    data = helper.read_raw(file_name, bucket)
    return pd.read_csv(io.BytesIO(data), dtype={"geoid": str})


def process(fetch_date: date | None = None, year: int = acs.ACS_YEAR, start_date: date | None = None, end_date: date | None = None):
    """Clean and join the raw files fetched on fetch_date (default today), then save joined.csv and summary.csv.
    The 311 and weather files cover the 2 days before fetch_date, same as the fetch services."""
    bucket = helper.configured_bucket()
    if fetch_date is None:
        fetch_date = date.today()
    start_date, end_date = helper.resolve_dates(start_date, end_date, fetch_date)
    sf311_data = retrieve_data_from_gcs(sf311.file_names(fetch_date, start_date, end_date)[1], bucket)
    acs_data = retrieve_data_from_gcs(acs.file_names(fetch_date, year)[1], bucket)
    weather_data = retrieve_data_from_gcs(weather.file_names(fetch_date, start_date, end_date)[1], bucket)
    tracts_data = retrieve_data_from_gcs(neighborhoods.file_names(fetch_date)[1], bucket)

    # 311: hours to close each case, keep only closed cases
    hours = pd.to_datetime(sf311_data["closed_date"]) - pd.to_datetime(sf311_data["created_date"])
    sf311_data["hours_to_close"] = hours.dt.total_seconds() / 3600
    sf311_data["date"] = sf311_data["created_date"].str[:10]
    sf311_data = sf311_data[sf311_data["hours_to_close"] >= 0]

    # Census: give each tract its neighborhood, then average income and total population per neighborhood
    acs_data = acs_data.dropna(subset=["median_household_income"]).merge(tracts_data, on="geoid")
    income = acs_data.groupby("neighborhood").agg({"median_household_income": "mean", "total_population": "sum"}).reset_index()

    # Weather: one row per day
    weather_data["date"] = weather_data["time"].str[:10]
    daily = weather_data.groupby("date").agg({"precipitation": "sum", "temperature_2m": "mean"}).reset_index()

    # Join: 311 + income on neighborhood, + weather on date
    joined = sf311_data.merge(income, on="neighborhood").merge(daily, on="date", how="left")
    summary = joined.groupby("neighborhood").agg({"median_household_income": "mean", "total_population": "mean",
                                                  "service_request_id": "count", "hours_to_close": "median"}).reset_index()
    summary = summary.rename(columns={"service_request_id": "cases", "hours_to_close": "median_hours"})

    upload_to_gcs(JOINED_PATH, joined.to_csv(index=False), content_type="text/csv", bucket=bucket)
    upload_to_gcs(SUMMARY_PATH, summary.to_csv(index=False), content_type="text/csv", bucket=bucket)
    return {"cases": len(joined), "neighborhoods": len(summary)}


def get_data():
    """Return the joined 311 cases for the dashboard."""
    return json.loads(retrieve_data_from_gcs(JOINED_PATH).to_json(orient="records"))


def get_summary():
    """Return one row per neighborhood: income, population, number of cases, median hours to close."""
    return json.loads(retrieve_data_from_gcs(SUMMARY_PATH).to_json(orient="records"))
