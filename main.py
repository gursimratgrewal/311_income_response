"""
This is the file that scrapes and calls from all 3 data sources 

To run:
  pip install -r requirements.txt
  cp .env_template .env  (Use this to fill it in)
  uvicorn main:app --reload
Then go to http://127.0.0.1:8000/docs and hit the endpoints.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Iterator, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingestion")


# Settings (all from .env)

def env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def csv_list(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_points(raw: str) -> List[Tuple[float, float]]:
    points = []
    for chunk in raw.split(";"):
        if chunk.strip():
            lat, lon = chunk.split(",")
            points.append((float(lat), float(lon)))
    if not points:
        raise ValueError("WEATHER_POINTS needs at least one 'lat,lon' pair")
    return points


STORAGE_BACKEND = env("STORAGE_BACKEND", "gcs").lower()
GCP_PROJECT_ID = env("GCP_PROJECT_ID")
GCS_BUCKET_NAME = env("GCS_BUCKET_NAME")
LOCAL_OUTPUT_DIR = env("LOCAL_OUTPUT_DIR", "./data")
RAW_PREFIX = env("RAW_PREFIX", "raw").strip("/")
HTTP_TIMEOUT = int(env("HTTP_TIMEOUT_SECONDS", "120"))

SF311_BASE_URL = env("SF311_BASE_URL", "https://data.sfgov.org/resource/vw6y-z8j6.json")
SF311_APP_TOKEN = env("SF311_APP_TOKEN")
SF311_PAGE_SIZE = min(int(env("SF311_PAGE_SIZE", "50000")), 50000)

CENSUS_API_KEY = env("CENSUS_API_KEY")
ACS_YEAR = int(env("ACS_YEAR", "2023"))
ACS_STATE_FIPS = env("ACS_STATE_FIPS", "06")
ACS_COUNTY_FIPS = env("ACS_COUNTY_FIPS", "075")
ACS_VARIABLES = csv_list(env("ACS_VARIABLES", "NAME,B19013_001E,B19013_001M,B01003_001E"))
TIGER_YEAR = int(env("TIGER_YEAR", str(ACS_YEAR)))

OPEN_METEO_BASE_URL = env(
    "OPEN_METEO_BASE_URL", "https://historical-forecast-api.open-meteo.com/v1/forecast"
)
OPEN_METEO_HOURLY_VARS = csv_list(env(
    "OPEN_METEO_HOURLY_VARS",
    "temperature_2m,relative_humidity_2m,precipitation,rain,weather_code,wind_speed_10m",
))
WEATHER_POINTS = parse_points(env(
    "WEATHER_POINTS",
    "37.795,-122.495;37.795,-122.445;37.795,-122.405;"
    "37.760,-122.495;37.760,-122.445;37.760,-122.400;"
    "37.725,-122.480;37.725,-122.440;37.725,-122.395",
))
TIMEZONE = env("TIMEZONE", "America/Los_Angeles")
WEATHER_DAYS_PER_REQUEST = 92 


# Helpers

class UpstreamError(RuntimeError):
    """One of the APIs sent back an error."""


@lru_cache(maxsize=1)
def get_session() -> requests.Session:
    # Retries a few times if an API is busy or rate limits us.
    retry = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "311-income-response-ingestion/1.0"
    return session


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# GCS Bucket and Storage

class Storage:
    """Saves files to the GCS bucket, or to a local folder in local mode."""

    def __init__(self):
        if STORAGE_BACKEND == "gcs":
            if not GCS_BUCKET_NAME:
                raise RuntimeError("GCS_BUCKET_NAME is empty. Set it in .env.")
            from google.cloud import storage
            self.bucket = storage.Client(project=GCP_PROJECT_ID).bucket(GCS_BUCKET_NAME)
        elif STORAGE_BACKEND == "local":
            self.bucket = None
        else:
            raise RuntimeError(f"STORAGE_BACKEND must be 'gcs' or 'local', got '{STORAGE_BACKEND}'.")

    def write_bytes(self, path: str, data: bytes, content_type: str) -> str:
        if self.bucket is not None:
            self.bucket.blob(path).upload_from_string(data, content_type=content_type, timeout=300)
            return f"gs://{GCS_BUCKET_NAME}/{path}"
        full = Path(LOCAL_OUTPUT_DIR) / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)
        return str(full.resolve())

    def write_ndjson(self, path: str, records: Iterable[dict]) -> str:
        # One JSON record per line. BigQuery can load this directly.
        lines = [json.dumps(r, ensure_ascii=False, default=str) for r in records]
        payload = "\n".join(lines) + ("\n" if lines else "")
        return self.write_bytes(path, payload.encode("utf-8"), "application/x-ndjson")

    def write_json(self, path: str, obj: Any) -> str:
        payload = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
        return self.write_bytes(path, payload.encode("utf-8"), "application/json")


@lru_cache(maxsize=1)
def get_storage() -> Storage:
    return Storage()


def save_manifest(storage: Storage, base: str, manifest: dict) -> dict:
    manifest_uri = storage.write_json(f"{base}/_manifest.json", manifest)
    return {**manifest, "manifest": manifest_uri}


# Source 1: SF 311 cases

def fetch_sf311_pages(
    session: requests.Session, start_date: date, end_date: date, max_records: Optional[int] = None
) -> Iterator[List[dict]]:
    end_exclusive = end_date + timedelta(days=1)
    where = (
        f"requested_datetime >= '{start_date.isoformat()}T00:00:00' "
        f"AND requested_datetime < '{end_exclusive.isoformat()}T00:00:00'"
    )
    headers = {"X-App-Token": SF311_APP_TOKEN} if SF311_APP_TOKEN else {}

    offset = fetched = 0
    while True:
        limit = SF311_PAGE_SIZE
        if max_records is not None:
            if fetched >= max_records:
                break
            limit = min(limit, max_records - fetched)

        params = {"$where": where, "$order": ":id", "$limit": limit, "$offset": offset}
        resp = session.get(SF311_BASE_URL, params=params, headers=headers, timeout=HTTP_TIMEOUT)
        if resp.status_code != 200:
            raise UpstreamError(f"[sf311] HTTP {resp.status_code}: {resp.text[:500]}")

        rows = resp.json()
        if not rows:
            break
        yield rows
        fetched += len(rows)
        offset += len(rows)
        if len(rows) < limit:
            break


def ingest_sf311_data(
    session: requests.Session, storage: Storage, start_date: date, end_date: date,
    max_records: Optional[int] = None,
) -> dict:
    run_id = new_run_id()
    base = f"{RAW_PREFIX}/sf311/requested_{start_date}_to_{end_date}/run_{run_id}"
    files, total = [], 0
    for i, page in enumerate(fetch_sf311_pages(session, start_date, end_date, max_records), start=1):
        files.append(storage.write_ndjson(f"{base}/part-{i:05d}.ndjson", page))
        total += len(page)
    return save_manifest(storage, base, {
        "source": "sf311", "source_url": SF311_BASE_URL, "run_id": run_id,
        "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
        "max_records": max_records, "record_count": total, "files": files,
    })


# Source 2: Census ACS + tract boundaries

def fetch_acs(session: requests.Session, year: int) -> List[dict]:
    url = f"https://api.census.gov/data/{year}/acs/acs5"
    params = {
        "get": ",".join(ACS_VARIABLES),
        "for": "tract:*",
        "in": f"state:{ACS_STATE_FIPS} county:{ACS_COUNTY_FIPS}",
    }
    if CENSUS_API_KEY:
        params["key"] = CENSUS_API_KEY

    resp = session.get(url, params=params, timeout=HTTP_TIMEOUT)
    if resp.status_code != 200:
        raise UpstreamError(f"[acs5] HTTP {resp.status_code}: {resp.text[:500]}")
    try:
        table = resp.json()
    except ValueError:
        # A bad or unactivated key gets an HTML page back instead of JSON.
        raise UpstreamError(
            "[acs5] Didn't get JSON back. Check CENSUS_API_KEY and ACS_YEAR. "
            f"Response starts with: {resp.text[:200]!r}"
        )

    header, rows = table[0], table[1:]
    records = []
    for row in rows:
        rec = dict(zip(header, row))
        rec["GEOID"] = f"{rec['state']}{rec['county']}{rec['tract']}" 
        rec["acs_year"] = year
        records.append(rec)
    return records


def ingest_acs_data(session: requests.Session, storage: Storage, year: int) -> dict:
    run_id = new_run_id()
    records = fetch_acs(session, year)
    base = f"{RAW_PREFIX}/acs5/year_{year}/run_{run_id}"
    data_uri = storage.write_ndjson(f"{base}/sf_tracts.ndjson", records)
    return save_manifest(storage, base, {
        "source": "acs5", "source_url": f"https://api.census.gov/data/{year}/acs/acs5",
        "run_id": run_id, "year": year, "variables": ACS_VARIABLES,
        "state_fips": ACS_STATE_FIPS, "county_fips": ACS_COUNTY_FIPS,
        "record_count": len(records), "files": [data_uri],
    })


def ingest_tract_boundaries(session: requests.Session, storage: Storage, year: int) -> dict:
    # Tract shapes, so we can figure out which tract each 311 case is in.
    url = f"https://www2.census.gov/geo/tiger/TIGER{year}/TRACT/tl_{year}_{ACS_STATE_FIPS}_tract.zip"
    resp = session.get(url, timeout=max(HTTP_TIMEOUT, 300))
    if resp.status_code != 200:
        raise UpstreamError(f"[census_tracts] HTTP {resp.status_code} for {url}")

    run_id = new_run_id()
    base = f"{RAW_PREFIX}/census_tracts/year_{year}/run_{run_id}"
    data_uri = storage.write_bytes(
        f"{base}/tl_{year}_{ACS_STATE_FIPS}_tract.zip", resp.content, "application/zip"
    )
    return save_manifest(storage, base, {
        "source": "census_tracts", "source_url": url, "run_id": run_id, "year": year,
        "size_bytes": len(resp.content), "files": [data_uri],
    })


# Source 3: Open-Meteo weather

def date_windows(start: date, end: date, max_days: int) -> Iterator[Tuple[date, date]]:
    cur = start
    while cur <= end:
        w_end = min(end, cur + timedelta(days=max_days - 1))
        yield cur, w_end
        cur = w_end + timedelta(days=1)


def fetch_weather_window(session: requests.Session, start: date, end: date) -> List[dict]:
    params = {
        "latitude": ",".join(str(lat) for lat, _ in WEATHER_POINTS),
        "longitude": ",".join(str(lon) for _, lon in WEATHER_POINTS),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": ",".join(OPEN_METEO_HOURLY_VARS),
        "timezone": TIMEZONE,
    }
    resp = session.get(OPEN_METEO_BASE_URL, params=params, timeout=HTTP_TIMEOUT)
    try:
        payload = resp.json()
    except ValueError:
        raise UpstreamError(f"[open_meteo] HTTP {resp.status_code}: not JSON {resp.text[:300]!r}")
    if resp.status_code != 200 or (isinstance(payload, dict) and payload.get("error")):
        reason = payload.get("reason") if isinstance(payload, dict) else resp.text[:300]
        raise UpstreamError(f"[open_meteo] HTTP {resp.status_code}: {reason}")

    locations = payload if isinstance(payload, list) else [payload]

    records = []
    for idx, ((req_lat, req_lon), loc) in enumerate(zip(WEATHER_POINTS, locations)):
        hourly = loc.get("hourly", {})
        for i, t in enumerate(hourly.get("time", [])):
            rec = {
                "location_id": idx,
                "request_latitude": req_lat,
                "request_longitude": req_lon,
                "grid_latitude": loc.get("latitude"),
                "grid_longitude": loc.get("longitude"),
                "elevation": loc.get("elevation"),
                "timezone": loc.get("timezone"),
                "time": t,
            }
            for var in OPEN_METEO_HOURLY_VARS:
                values = hourly.get(var)
                rec[var] = values[i] if values is not None and i < len(values) else None
            records.append(rec)
    return records


def ingest_weather_data(
    session: requests.Session, storage: Storage, start_date: date, end_date: date
) -> dict:
    run_id = new_run_id()
    base = f"{RAW_PREFIX}/open_meteo/{start_date}_to_{end_date}/run_{run_id}"
    files, total = [], 0
    for i, (w_start, w_end) in enumerate(
        date_windows(start_date, end_date, WEATHER_DAYS_PER_REQUEST), start=1
    ):
        records = fetch_weather_window(session, w_start, w_end)
        files.append(storage.write_ndjson(f"{base}/part-{i:05d}.ndjson", records))
        total += len(records)
    return save_manifest(storage, base, {
        "source": "open_meteo", "source_url": OPEN_METEO_BASE_URL, "run_id": run_id,
        "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
        "points": WEATHER_POINTS, "hourly_variables": OPEN_METEO_HOURLY_VARS,
        "timezone": TIMEZONE, "record_count": total, "files": files,
    })


# FastAPI app

app = FastAPI(
    title="311 Income Response - Data Ingestion API",
    description="Pulls SF 311, Census, and weather data and saves it to our GCS bucket.",
    version="1.0.0",
)


def resolve_dates(start: Optional[date], end: Optional[date]) -> Tuple[date, date]:
    end = end or (date.today() - timedelta(days=1))
    start = start or (end - timedelta(days=6))
    if start > end:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date")
    return start, end


def run_job(name: str, fn, *args) -> dict:
    try:
        log.info("Starting %s", name)
        result = fn(get_session(), get_storage(), *args)
        log.info("Finished %s: %s rows", name, result.get("record_count", "n/a"))
        return result
    except UpstreamError as exc:
        log.error("%s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except requests.RequestException as exc:
        log.error("[%s] network error: %s", name, exc)
        raise HTTPException(status_code=502, detail=f"[{name}] network error: {exc}")
    except RuntimeError as exc:
        log.error("Config error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "storage_backend": STORAGE_BACKEND,
        "bucket": GCS_BUCKET_NAME if STORAGE_BACKEND == "gcs" else LOCAL_OUTPUT_DIR,
        "census_api_key_set": bool(CENSUS_API_KEY),
        "sf311_app_token_set": bool(SF311_APP_TOKEN),
        "acs_year": ACS_YEAR,
        "weather_points": len(WEATHER_POINTS),
    }


@app.post("/ingest/sf311")
def ingest_sf311(
    start_date: Optional[date] = Query(None, description="YYYY-MM-DD. Default: 7 days ago."),
    end_date: Optional[date] = Query(None, description="YYYY-MM-DD. Default: yesterday."),
    max_records: Optional[int] = Query(None, ge=1, description="Row limit, handy for testing."),
) -> dict:
    start, end = resolve_dates(start_date, end_date)
    return run_job("sf311", ingest_sf311_data, start, end, max_records)


@app.post("/ingest/acs")
def ingest_acs(
    year: Optional[int] = Query(None, ge=2009, description="Default: ACS_YEAR from .env."),
) -> dict:
    return run_job("acs5", ingest_acs_data, year or ACS_YEAR)


@app.post("/ingest/census-tracts")
def ingest_census_tracts(
    year: Optional[int] = Query(None, ge=2010, description="Default: TIGER_YEAR from .env."),
) -> dict:
    return run_job("census_tracts", ingest_tract_boundaries, year or TIGER_YEAR)


@app.post("/ingest/weather")
def ingest_weather(
    start_date: Optional[date] = Query(None, description="YYYY-MM-DD. Default: 7 days ago."),
    end_date: Optional[date] = Query(None, description="YYYY-MM-DD. Default: yesterday."),
) -> dict:
    start, end = resolve_dates(start_date, end_date)
    return run_job("open_meteo", ingest_weather_data, start, end)


@app.post("/ingest/all")
def ingest_all(
    start_date: Optional[date] = Query(None, description="Dates for 311 and weather. Default: last 7 days."),
    end_date: Optional[date] = Query(None),
    max_records: Optional[int] = Query(None, ge=1, description="Row limit for 311."),
) -> dict:
    # Runs everything. If one source fails, the rest still run.
    start, end = resolve_dates(start_date, end_date)
    jobs = [
        ("sf311", ingest_sf311_data, (start, end, max_records)),
        ("acs5", ingest_acs_data, (ACS_YEAR,)),
        ("census_tracts", ingest_tract_boundaries, (TIGER_YEAR,)),
        ("open_meteo", ingest_weather_data, (start, end)),
    ]
    results, errors = {}, {}
    for name, fn, args in jobs:
        try:
            results[name] = run_job(name, fn, *args)
        except HTTPException as exc:
            errors[name] = exc.detail
    return {"start_date": start, "end_date": end, "results": results, "errors": errors}
