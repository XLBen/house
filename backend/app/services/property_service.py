"""房源查询服务：列表筛选、详情、价格历史、事件。"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import Event, PriceHistory, Property, RegionProperty
from ..schemas.property import PriceHistoryOut, PropertyDetail, PropertyListItem
from .dates import now_utc

# 类型家族归一化：筛选 "house"/"flat" 时匹配实际命名
_TYPE_FAMILIES = {
    "house": (
        "house", "terraced house", "semi-detached house", "detached house",
        "bungalow", "town house", "cottage",
    ),
    "flat": ("flat", "apartment", "maisonette", "studio"),
}

_ACTIVE = ("listed", "under_offer", "sold")

_SORT_MAP = {
    "price_desc": Property.current_price.desc(),
    "price_asc": Property.current_price.asc(),
    "newest": Property.first_seen_at.desc(),
    "beds_desc": Property.bedrooms.desc(),
    "reduced": Property.reduced_flag.desc(),
    "oldest": Property.first_seen_at.asc(),
}


def expand_types(property_type: str) -> list[str]:
    raw = [t.strip().lower() for t in property_type.split(",") if t.strip()]
    expanded: list[str] = []
    for t in raw:
        family = _TYPE_FAMILIES.get(t)
        if family:
            expanded.extend(family)
        else:
            expanded.append(t)
    return expanded


def enrich_item(db: Session, prop: Property) -> PropertyListItem:
    item = PropertyListItem.model_validate(prop)
    first = (
        db.query(PriceHistory)
        .filter(PriceHistory.property_id == prop.id)
        .order_by(PriceHistory.captured_at.asc())
        .first()
    )
    if first:
        item.first_price = first.price
        if first.price and prop.current_price:
            item.pct_change = round(
                (prop.current_price - first.price) / first.price * 100, 1
            )
    if prop.current_price and prop.floor_area_sqft:
        item.price_per_sqft = round(prop.current_price / prop.floor_area_sqft)
    return item


def list_region_properties(
    db: Session,
    region_id: int,
    *,
    status: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    bedrooms: int | None = None,
    property_type: str | None = None,
    has_image: bool | None = None,
    min_image_count: int | None = None,
    new_in_days: int | None = None,
    q: str | None = None,
    sort: str = "price_desc",
    page: int = 1,
    page_size: int = 24,
) -> dict:
    query = (
        db.query(Property)
        .join(RegionProperty, RegionProperty.property_id == Property.id)
        .filter(RegionProperty.region_id == region_id)
    )
    if status:
        query = query.filter(Property.status == status)
    else:
        query = query.filter(Property.status.in_(_ACTIVE))
    if min_price is not None:
        query = query.filter(Property.current_price >= min_price)
    if max_price is not None:
        query = query.filter(Property.current_price <= max_price)
    if bedrooms is not None:
        query = query.filter(Property.bedrooms == bedrooms)
    if property_type:
        types = expand_types(property_type)
        if types:
            query = query.filter(Property.property_type.in_(types))
    if new_in_days is not None and new_in_days > 0:
        query = query.filter(
            Property.first_seen_at >= now_utc() - timedelta(days=new_in_days)
        )
    if has_image:
        query = query.filter(Property.image_url.isnot(None))
    if min_image_count is not None:
        query = query.filter(Property.image_count >= min_image_count)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Property.address.ilike(like),
                Property.postcode.ilike(like),
                Property.town.ilike(like),
            )
        )

    total = query.count()
    items = (
        query.order_by(_SORT_MAP.get(sort, Property.current_price.desc()))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [enrich_item(db, p) for p in items],
    }


def get_property_detail(db: Session, prop: Property) -> PropertyDetail:
    history = (
        db.query(PriceHistory)
        .filter(PriceHistory.property_id == prop.id)
        .order_by(PriceHistory.captured_at.asc())
        .all()
    )
    item = enrich_item(db, prop)
    detail = PropertyDetail.model_validate(item.model_dump())
    detail.description = prop.description
    detail.price_history = [PriceHistoryOut.model_validate(h) for h in history]
    return detail


def get_price_history(db: Session, property_id: int) -> list:
    return (
        db.query(PriceHistory)
        .filter(PriceHistory.property_id == property_id)
        .order_by(PriceHistory.captured_at.asc())
        .all()
    )


def get_property_events(db: Session, property_id: int) -> list:
    return (
        db.query(Event)
        .filter(Event.property_id == property_id)
        .order_by(Event.occurred_at.desc())
        .all()
    )
