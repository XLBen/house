"""区域管理服务。"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..identity.fingerprint import normalize_postcode
from ..models import Region
from ..schemas.region import RegionCreate, RegionUpdate
from .geocoder import geocode_postcode

logger = logging.getLogger(__name__)


def create_region(db: Session, data: RegionCreate) -> Region:
    postcode = normalize_postcode(data.center_postcode)
    _ensure_unique_search(db, postcode, data.radius_km)
    region = Region(
        name=data.name,
        center_postcode=postcode,
        radius_km=data.radius_km,
        is_active=data.is_active,
    )
    point = geocode_postcode(region.center_postcode)
    if point:
        region.center_lat, region.center_lng = point
    db.add(region)
    db.commit()
    db.refresh(region)
    return region


def update_region(db: Session, region: Region, data: RegionUpdate) -> Region:
    changes = data.model_dump(exclude_unset=True)
    postcode = normalize_postcode(changes["center_postcode"]) if "center_postcode" in changes else region.center_postcode
    radius = changes.get("radius_km", region.radius_km)
    if (
        changes.get("is_active", region.is_active)
        and ("center_postcode" in changes or "radius_km" in changes or changes.get("is_active"))
    ):
        _ensure_unique_search(db, postcode, radius, exclude_id=region.id)
    for key, value in changes.items():
        setattr(region, key, value)
    if "center_postcode" in changes:
        region.center_postcode = postcode
        point = geocode_postcode(region.center_postcode)
        # 地理编码失败时保留原坐标，避免瞬时网络问题摧毁区域中心点
        if point:
            region.center_lat, region.center_lng = point
    db.commit()
    db.refresh(region)
    return region


def _ensure_unique_search(
    db: Session, postcode: str, radius_km: float, exclude_id: int | None = None
) -> None:
    query = db.query(Region).filter(
        Region.center_postcode == postcode,
        Region.radius_km == radius_km,
        Region.is_active.is_(True),
    )
    if exclude_id is not None:
        query = query.filter(Region.id != exclude_id)
    if query.first() is not None:
        raise ValueError(f"相同邮编和半径的活跃区域已存在: {postcode} / {radius_km}km")


def delete_region(db: Session, region: Region) -> None:
    from ..models import Event, RegionProperty, RegionSnapshot, SyncRun

    db.query(RegionProperty).filter(RegionProperty.region_id == region.id).delete()
    db.query(RegionSnapshot).filter(RegionSnapshot.region_id == region.id).delete()
    db.query(SyncRun).filter(SyncRun.region_id == region.id).delete()
    db.query(Event).filter(Event.region_id == region.id).delete()
    db.delete(region)
    db.commit()
