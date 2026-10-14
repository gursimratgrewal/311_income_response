"""Shared data types for SF 311, Census ACS, neighborhoods, and weather."""

from datetime import date, datetime
from pydantic import BaseModel


class ACSTract(BaseModel):
    """One SF census tract from the ACS 5-year data."""
    geoid: str
    tract_name: str
    median_household_income: int | None = None
    total_population: int | None = None
    acs_year: int


class WeatherHour(BaseModel):
    """Hourly SF weather data from Open-Meteo."""
    time: datetime
    lat: float
    lng: float
    temperature_2m: float | None = None
    precipitation: float | None = None
    rain: float | None = None
    weather_code: int | None = None
    wind_speed_10m: float | None = None


class SF311Case(BaseModel):
    """One SF 311 service request from the CSV source."""
    service_request_id: int
    created_date: datetime
    closed_date: datetime | None = None
    updated_date: datetime | None = None
    status: str | None = None
    responsible_agency: str | None = None
    service_category: str | None = None
    request_type: str | None = None
    supervisor_dist: str | None = None
    neighborhood: str | None = None
    police_dist: str | None = None
    lat: float | None = None
    lng: float | None = None
    source: str | None = None


class StoreData(BaseModel):
    """What each store route returns."""
    rows_saved: int
    rows_skipped: int
    gcs_path: str


class TractNeighborhood(BaseModel):
    """census tract mapped to neighborhood."""
    geoid: str
    tract_name: str
    neighborhood: str
    supervisor_dist: str | None = None


class FetchData(BaseModel):
    source: str
    fetched_date: date
    raw_data_type: str
    gcs_path: str
    year: int | None = None
    start_date: date | None = None
    end_date: date | None = None
