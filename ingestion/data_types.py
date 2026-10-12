
"""Data types for SF 311 cases file fetch data. """

from datetime import datetime
from pydantic import BaseModel

class SF311Case(BaseModel):
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

class FetchData(BaseModel):
    rows_saved: int
    rows_skipped: int
    gcs_path: str

