from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .stats import RegionStatsOut


class RegionCreate(BaseModel):
    name: str
    center_postcode: str
    radius_km: float = 2.0
    is_active: bool = True


class RegionUpdate(BaseModel):
    name: str | None = None
    center_postcode: str | None = None
    radius_km: float | None = None
    is_active: bool | None = None


class SyncRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    region_id: int | None
    started_at: datetime
    finished_at: datetime | None
    status: str
    data_source: str = "unknown"
    complete: bool | None = True
    new_count: int
    changed_count: int
    price_changed_count: int = 0
    status_changed_count: int = 0
    delisted_count: int
    error: str | None


class RegionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    center_postcode: str
    radius_km: float
    center_lat: float | None
    center_lng: float | None
    is_active: bool
    last_synced_at: datetime | None
    created_at: datetime
    stats: RegionStatsOut | None = None
    last_sync: SyncRunOut | None = None
