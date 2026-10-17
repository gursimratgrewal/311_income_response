"""shared helper functions"""

import requests
import pandas as pd
from datetime import timedelta
from fastapi import HTTPException
from pydantic import ValidationError

from storage import get_bucket, retrieve_data_from_gcs
from user_definition import bucket_name, HTTP_TIMEOUT_SECONDS, LOOKBACK_DAYS


def configured_bucket():
    if not bucket_name:
        raise HTTPException(status_code=500, detail="Bucket name is not configured")
    return get_bucket()


def resolve_dates(start_date, end_date, today):
    if end_date is None:
        end_date = today - timedelta(days=1)
    if start_date is None:
        start_date = end_date - timedelta(days=LOOKBACK_DAYS)
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    return [start_date, end_date]


def fetch_response(url, params=None):
    try:
        response = requests.get(url, params=params, timeout=HTTP_TIMEOUT_SECONDS)
    except:
        raise HTTPException(status_code=502, detail="Failed to fetch data from source")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch data from source")
    return response


def read_raw(file_name, bucket):
    try:
        return retrieve_data_from_gcs(file_name, bucket)
    except:
        raise HTTPException(status_code=404, detail=f"Raw file not found: {file_name}")


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
