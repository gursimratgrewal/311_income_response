import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID")
bucket_name = os.getenv("GCP_BUCKET_NAME")
service_account_key = os.getenv("GCP_SERVICE_ACCOUNT_KEY")
census_api_key = os.getenv("CENSUS_API_KEY")

RAW_PREFIX = "raw"
HTTP_TIMEOUT_SECONDS = 120
LOOKBACK_DAYS = 1

JOINED_PATH = "processed/joined.csv"
SUMMARY_PATH = "processed/summary.csv"

ACS_URL = "https://api.census.gov/data/{year}/acs/acs5"
ACS_YEAR = 2024
ACS_VARS = "NAME,B19013_001E,B01003_001E"
STATE_FIPS = "06"
COUNTY_FIPS = "075"

NEIGHBORHOOD_URL = "https://data.sfgov.org/api/views/sevw-6tgi/rows.csv?accessType=DOWNLOAD"
NEIGHBORHOOD_VARS = { "geoid": "geoid",
    "name": "tract_name",
    "neighborhoods_analysis_boundaries": "neighborhood",
    "sup_dist_2022": "supervisor_dist",
}

WEATHER_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
SF_LAT = 37.7749
SF_LNG = -122.4194
SF_TIMEZONE = "America/Los_Angeles"
WEATHER_VARS = ["temperature_2m", "precipitation", "rain", "weather_code", "wind_speed_10m"]

SF311_URL = "https://data.sfgov.org/resource/vw6y-z8j6.csv"
SF311_LIMIT = 100000
SF311_VARS = {
    "service_request_id": "service_request_id",
    "requested_datetime": "created_date",
    "closed_date": "closed_date",
    "updated_datetime": "updated_date",
    "status_description": "status",
    "agency_responsible": "responsible_agency",
    "service_name": "service_category",
    "service_subtype": "request_type",
    "supervisor_district": "supervisor_dist",
    "analysis_neighborhood": "neighborhood",
    "police_district": "police_dist",
    "lat": "lat",
    "long": "lng",
    "source": "source",
}
SF311_DATES = ["created_date", "closed_date", "updated_date"]