from datetime import datetime

from pydantic import BaseModel

from .property import EventOut


class ChangeItem(BaseModel):
    event: EventOut
    listing_id: str
    address: str | None
    bedrooms: int | None
    property_type: str | None
    url: str | None
    status: str


class ChangeSummary(BaseModel):
    date: str
    is_first_sync: bool = False
    new: list[ChangeItem] = []
    price_changes: list[ChangeItem] = []
    status_changes: list[ChangeItem] = []
    delisted: list[ChangeItem] = []


class TrendPoint(BaseModel):
    date: str
    active_count: int
    avg_price: float | None


class RegionStatsOut(BaseModel):
    region_id: int = 0
    date: str = ""
    active_count: int = 0
    avg_price: float | None = None
    median_price: float | None = None
    min_price: int | None = None
    max_price: int | None = None
    new_today: int = 0
    price_changes_today: int = 0
    delisted_today: int = 0
    recent_added: list = []
    recent_removed: list = []
    biggest_drops: list = []
    trend: list[TrendPoint] = []


class MapPointOut(BaseModel):
    id: int
    listing_id: str
    lat: float | None
    lng: float | None
    price: int | None
    status: str
    address: str | None


class RegionMapOut(BaseModel):
    region_id: int
    center_lat: float | None
    center_lng: float | None
    radius_km: float
    points: list[MapPointOut]
