from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PropertyListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: str
    address: str | None
    postcode: str | None
    town: str | None
    bedrooms: int | None
    bathrooms: int | None
    property_type: str | None
    current_price: int | None
    status: str
    lat: float | None
    lng: float | None
    url: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    floor_area_sqft: float | None = None
    image_url: str | None = None
    image_count: int | None = None
    removed_at: datetime | None = None
    relisted_at: datetime | None = None
    reduced_flag: bool | None = None
    added_hint: str | None = None
    new_home_flag: bool | None = None
    # 由服务端计算，非 ORM 字段
    first_price: int | None = None
    pct_change: float | None = None
    price_per_sqft: int | None = None


class PriceHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    price: int
    captured_at: datetime


class PropertyDetail(PropertyListItem):
    description: str | None = None
    price_history: list[PriceHistoryOut] = []


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    region_id: int | None
    event_type: str
    old_value: str | None
    new_value: str | None
    occurred_at: datetime
