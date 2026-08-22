"""收藏与导出服务。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import (
    Event,
    PriceHistory,
    Property,
    PropertyWatch,
    Region,
    RegionProperty,
    RegionSnapshot,
    SyncRun,
)
from .dates import now_utc


def _regions_by_property(db: Session, property_ids: list[int]) -> dict[int, list[dict]]:
    if not property_ids:
        return {}
    rows = (
        db.query(RegionProperty.property_id, Region.id, Region.name)
        .join(Region, Region.id == RegionProperty.region_id)
        .filter(RegionProperty.property_id.in_(property_ids))
        .all()
    )
    result: dict[int, list[dict]] = {pid: [] for pid in property_ids}
    for pid, rid, rname in rows:
        result[pid].append({"id": rid, "name": rname})
    return result


def _to_watch_item(p: Property, regions: list[dict]) -> dict:
    return {
        "id": p.id,
        "listing_id": p.listing_id,
        "address": p.address,
        "price": p.current_price,
        "bedrooms": p.bedrooms,
        "property_type": p.property_type,
        "image_url": p.image_url,
        "status": p.status,
        "removed_at": p.removed_at,
        "url": p.url,
        "regions": regions,
    }


def watchlist(db: Session) -> list[dict]:
    rows = (
        db.query(Property)
        .join(PropertyWatch, PropertyWatch.property_id == Property.id)
        .order_by(PropertyWatch.created_at.desc())
        .all()
    )
    region_map = _regions_by_property(db, [p.id for p in rows])
    return [_to_watch_item(p, region_map.get(p.id, [])) for p in rows]


def watch_check(db: Session, property_id: int) -> bool:
    return (
        db.query(PropertyWatch)
        .filter(PropertyWatch.property_id == property_id)
        .first()
        is not None
    )


def watch_add(db: Session, property_id: int) -> None:
    from sqlalchemy.exc import IntegrityError

    try:
        db.add(PropertyWatch(property_id=property_id, created_at=now_utc()))
        db.commit()
    except IntegrityError:
        db.rollback()


def watch_remove(db: Session, property_id: int) -> None:
    db.query(PropertyWatch).filter(PropertyWatch.property_id == property_id).delete()
    db.commit()


def export_all_json(db: Session) -> dict:
    """全量导出（JSON）——数据库可复用性：数据可被其他工具消费。"""
    props = db.query(Property).all()
    return {
        "exported_at": now_utc().isoformat(),
        "regions": [r.__dict__ for r in db.query(Region).all()],
        "properties": [
            {k: v for k, v in p.__dict__.items() if not k.startswith("_")}
            for p in props
        ],
        "region_properties": [
            rp.__dict__ for rp in db.query(RegionProperty).all()
        ],
        "price_history": [
            {k: v for k, v in ph.__dict__.items() if not k.startswith("_")}
            for ph in db.query(PriceHistory).all()
        ],
        "events": [
            {k: v for k, v in e.__dict__.items() if not k.startswith("_")}
            for e in db.query(Event).all()
        ],
        "snapshots": [
            {k: v for k, v in s.__dict__.items() if not k.startswith("_")}
            for s in db.query(RegionSnapshot).all()
        ],
        "sync_runs": [
            {k: v for k, v in r.__dict__.items() if not k.startswith("_")}
            for r in db.query(SyncRun).all()
        ],
    }
