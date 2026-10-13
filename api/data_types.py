"""Data types for the API fetch data from Census ACS and Open-Meteo weather. """

from datetime import datetime
from pydantic import BaseModel


class ACSTract(BaseModel):
    """One SF census tract from the ACS 5-year data."""
    geoid: str                              
    tract_name: str
    median_household_income: int | None = None
    total_population: int | None = None
    acs_year: int

class WeatherHour(BaseModel):
    """Hourly SF weather data from Open-Meteo"""
    time: datetime                          
    lat: float
    lng: float
    temperature_2m: float | None = None     
    precipitation: float | None = None      
    rain: float | None = None               
    weather_code: int | None = None        
    wind_speed_10m: float | None = None     

class FetchData(BaseModel):
    """What each fetch route returns."""
    rows_saved: int
    rows_skipped: int
    gcs_path: str
