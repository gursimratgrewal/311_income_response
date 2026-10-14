"""FastAPI routes"""

from datetime import date

from fastapi import FastAPI
from collectors import acs, neighborhoods, sf311, weather
from data_types import FetchData, StoreData
import transform

app = FastAPI()

@app.get("/")
def root():
    """Returns a welcome message from the api sources."""
    return {"message": "Welcome to the Census Data Fetch API"}


@app.get("/fetch/acs", response_model=FetchData)
def fetch_acs_data(year: int = acs.ACS_YEAR):
    """Gets the median household income and population for every SF census tract. Missing estimates are saved as blank."""
    return acs.fetch_acs_data(year)


@app.get("/parse/acs", response_model=StoreData)
def parse_acs_data(year: int = acs.ACS_YEAR, fetch_date: date | None = None):
    return acs.parse_acs_data(year, fetch_date)


@app.get("/fetch/weather", response_model=FetchData)
def fetch_weather_data(start_date: date | None = None, end_date: date | None = None):
    """Gets hourly SF weather between start_date and end_date from Open-Meteo. Default is the last 2 days ending yesterday."""
    return weather.fetch_weather_data(start_date, end_date)


@app.get("/parse/weather", response_model=StoreData)
def parse_weather_data(start_date: date | None = None, end_date: date | None = None, fetch_date: date | None = None):
    return weather.parse_weather_data(start_date, end_date, fetch_date)


@app.get("/fetch/sf311", response_model=FetchData)
def fetch_sf311_data(start_date: date | None = None, end_date: date | None = None):
    """Download SF 311 cases opened between start_date and end_date as a CSV file"""
    return sf311.fetch_sf311_data(start_date, end_date)


@app.get("/parse/sf311", response_model=StoreData)
def parse_sf311_data(start_date: date | None = None, end_date: date | None = None, fetch_date: date | None = None):
    return sf311.parse_sf311_data(start_date, end_date, fetch_date)


@app.get("/fetch/neighborhoods", response_model=FetchData)
def fetch_neighborhoods():
    """Download the SF census tract to neighborhood CSV file (file-based source)"""
    return neighborhoods.fetch_neighborhoods()


@app.get("/parse/neighborhoods", response_model=StoreData)
def parse_neighborhoods(fetch_date: date | None = None):
    return neighborhoods.parse_neighborhoods(fetch_date)


@app.post("/process")
def process(fetch_date: date | None = None, year: int = acs.ACS_YEAR, start_date: date | None = None, end_date: date | None = None):
    return transform.process(fetch_date, year, start_date, end_date)


@app.get("/data")
def get_data():
    """Return the joined 311 cases for the dashboard."""
    return transform.get_data()


@app.get("/summary")
def get_summary():
    """Return one row per neighborhood: income, population, number of cases, median hours to close."""
    return transform.get_summary()
