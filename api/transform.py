"""Part C - clean and join the 311, Census, weather and neighborhood files, and store the result in GCS."""

import json
from datetime import date, timedelta

import pandas as pd
from fastapi import FastAPI
from storage import retrieve_data_from_gcs, store_to_gcs

app = FastAPI()


@app.post("/process")
def process(fetch_date: date | None = None):
    """Clean and join the raw files fetched on fetch_date (default today), then save joined.csv and summary.csv.
    The 311 and weather files cover the 2 days before fetch_date, same as the fetch services."""
    if fetch_date is None:
        fetch_date = date.today()
    end_date = fetch_date - timedelta(days=1)
    start_date = end_date - timedelta(days=1)

    sf311 = retrieve_data_from_gcs(f"raw/sf311/{fetch_date}/sf311_{start_date}_to_{end_date}.csv")
    acs = retrieve_data_from_gcs(f"raw/acs/{fetch_date}/acs_2024.csv")
    weather = retrieve_data_from_gcs(f"raw/weather/{fetch_date}/weather_{start_date}_to_{end_date}.csv")
    tracts = retrieve_data_from_gcs(f"raw/neighborhoods/{fetch_date}/tract_neighborhoods.csv")

    # 311: hours to close each case, keep only closed cases
    hours = pd.to_datetime(sf311["closed_date"]) - pd.to_datetime(sf311["created_date"])
    sf311["hours_to_close"] = hours.dt.total_seconds() / 3600
    sf311["date"] = sf311["created_date"].str[:10]
    sf311 = sf311[sf311["hours_to_close"] >= 0]

    # Census: give each tract its neighborhood, then average income and total population per neighborhood
    acs = acs.dropna(subset=["median_household_income"]).merge(tracts, on="geoid")
    income = acs.groupby("neighborhood").agg({"median_household_income": "mean", "total_population": "sum"}).reset_index()

    # Weather: one row per day
    weather["date"] = weather["time"].str[:10]
    daily = weather.groupby("date").agg({"precipitation": "sum", "temperature_2m": "mean"}).reset_index()

    # Join: 311 + income on neighborhood, + weather on date
    joined = sf311.merge(income, on="neighborhood").merge(daily, on="date", how="left")
    summary = joined.groupby("neighborhood").agg({"median_household_income": "mean", "total_population": "mean",
                                                  "service_request_id": "count", "hours_to_close": "median"}).reset_index()
    summary = summary.rename(columns={"service_request_id": "cases", "hours_to_close": "median_hours"})

    store_to_gcs("processed/joined.csv", joined)
    store_to_gcs("processed/summary.csv", summary)
    return {"cases": len(joined), "neighborhoods": len(summary)}


@app.get("/data")
def get_data():
    """Return the joined 311 cases for the dashboard."""
    return json.loads(retrieve_data_from_gcs("processed/joined.csv").to_json(orient="records"))


@app.get("/summary")
def get_summary():
    """Return one row per neighborhood: income, population, number of cases, median hours to close."""
    return json.loads(retrieve_data_from_gcs("processed/summary.csv").to_json(orient="records"))
