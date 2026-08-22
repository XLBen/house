"""变化查询服务：为 API 提供每日变化与统计。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import (
    Event,
    PriceHistory,
    Property,
    Region,
    RegionProperty,
    RegionSnapshot,
    SyncRun,
)
from ..schemas.stats import ChangeItem, ChangeSummary, TrendPoint
from .dates import day_bounds, local_today


def _parse_since(since: str | None, region) -> datetime | None:
    """since 解析：'last_sync' 或 ISO 日期/时间。返回起始时间（含）。"""
    if not since:
        return None
    if since == "last_sync":
        if region is None or region.last_synced_at is None:
            return None
        return region.last_synced_at
    try:
        return datetime.fromisoformat(since)
    except ValueError:
        return None


def changes_for_region(
    db: Session,
    region_id: int,
    day: str | None = None,
    since: str | None = None,
) -> ChangeSummary:
    """按日期(day)或自 since 以来(since)返回变化。"""
    region = db.get(Region, region_id)
    if since:
        start = _parse_since(since, region)
        end = None
        label = since if since != "last_sync" else (
            start.isoformat() if start else "last_sync"
        )
    else:
        day = day or local_today()
        start, end = day_bounds(day)
        label = day

    query = (
        db.query(Event)
        .join(Property, Event.property_id == Property.id)
        .filter(Event.region_id == region_id, Event.occurred_at >= start)
    )
    if end is not None:
        query = query.filter(Event.occurred_at <= end)
    events = query.order_by(Event.occurred_at.desc()).all()

    props = _properties_by_ids(db, [ev.property_id for ev in events])
    summary = ChangeSummary(date=label)
    summary.is_first_sync = is_first_sync(db, region_id)
    for ev in events:
        item = _to_change_item(ev, props.get(ev.property_id))
        if ev.event_type == "new":
            summary.new.append(item)
        elif ev.event_type == "price_change":
            summary.price_changes.append(item)
        elif ev.event_type == "status_change":
            summary.status_changes.append(item)
        elif ev.event_type == "delisted":
            summary.delisted.append(item)
    return summary


def is_first_sync(db: Session, region_id: int) -> bool:
    """统一判定：该区域是否"刚完成首次同步"（只有一次成功同步记录）。

    sync 结果与 changes 端点共用此定义，杜绝两套语义漂移。
    """
    count = (
        db.query(SyncRun)
        .filter(SyncRun.region_id == region_id, SyncRun.status == "success")
        .count()
    )
    return count == 1


def _properties_by_ids(db: Session, property_ids: list[int]) -> dict[int, Property]:
    ids = list(dict.fromkeys(property_ids))
    if not ids:
        return {}
    rows = db.query(Property).filter(Property.id.in_(ids)).all()
    return {p.id: p for p in rows}


def _to_change_item(ev: Event, prop: Property | None) -> ChangeItem:
    return ChangeItem(
        event=ev,
        listing_id=prop.listing_id if prop else "",
        address=prop.address if prop else None,
        bedrooms=prop.bedrooms if prop else None,
        property_type=prop.property_type if prop else None,
        url=prop.url if prop else None,
        status=prop.status if prop else "removed",
    )


def region_stats(db: Session, region_id: int) -> dict:
    today = local_today()
    snapshot = (
        db.query(RegionSnapshot)
        .filter(RegionSnapshot.region_id == region_id, RegionSnapshot.date == today)
        .first()
    )
    trend = (
        db.query(RegionSnapshot)
        .filter(RegionSnapshot.region_id == region_id)
        .order_by(RegionSnapshot.date.asc())
        .all()
    )
    result = {
        "region_id": region_id,
        "date": today,
        "active_count": snapshot.active_count if snapshot else 0,
        "avg_price": snapshot.avg_price if snapshot else None,
        "median_price": snapshot.median_price if snapshot else None,
        "min_price": snapshot.min_price if snapshot else None,
        "max_price": snapshot.max_price if snapshot else None,
        "new_today": snapshot.new_count if snapshot else 0,
        "price_changes_today": snapshot.price_change_count if snapshot else 0,
        "delisted_today": snapshot.delisted_count if snapshot else 0,
        "recent_added": _recent_list(db, region_id, "listed", "first_seen_at", 5),
        "recent_removed": _recent_removed(db, region_id, 5),
        "biggest_drops": _biggest_drops(db, region_id, 5),
        "trend": [TrendPoint(**t.__dict__) for t in trend],
    }
    return result


def region_stats_light(db: Session, region_id: int) -> dict:
    """轻量统计（列表用）：只读当日快照的头部数字，不做 recent/trend 查询。"""
    today = local_today()
    snapshot = (
        db.query(RegionSnapshot)
        .filter(RegionSnapshot.region_id == region_id, RegionSnapshot.date == today)
        .first()
    )
    return {
        "region_id": region_id,
        "date": today,
        "active_count": snapshot.active_count if snapshot else 0,
        "avg_price": snapshot.avg_price if snapshot else None,
        "median_price": snapshot.median_price if snapshot else None,
        "min_price": snapshot.min_price if snapshot else None,
        "max_price": snapshot.max_price if snapshot else None,
        "new_today": snapshot.new_count if snapshot else 0,
        "price_changes_today": snapshot.price_change_count if snapshot else 0,
        "delisted_today": snapshot.delisted_count if snapshot else 0,
    }


def _recent_list(db: Session, region_id: int, status: str, order_col: str, limit: int) -> list:
    col = getattr(Property, order_col)
    props = (
        db.query(Property)
        .join(RegionProperty, RegionProperty.property_id == Property.id)
        .filter(RegionProperty.region_id == region_id, Property.status == status)
        .order_by(col.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": p.id,
            "listing_id": p.listing_id,
            "address": p.address,
            "price": p.current_price,
            "bedrooms": p.bedrooms,
            "property_type": p.property_type,
            "image_url": p.image_url,
            "status": p.status,
            "first_seen_at": p.first_seen_at,
            "removed_at": p.removed_at,
        }
        for p in props
    ]


def _recent_removed(db: Session, region_id: int, limit: int) -> list:
    props = (
        db.query(Property)
        .join(RegionProperty, RegionProperty.property_id == Property.id)
        .filter(
            RegionProperty.region_id == region_id,
            Property.status == "removed",
            Property.removed_at.isnot(None),
        )
        .order_by(Property.removed_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": p.id,
            "listing_id": p.listing_id,
            "address": p.address,
            "price": p.current_price,
            "bedrooms": p.bedrooms,
            "property_type": p.property_type,
            "image_url": p.image_url,
            "status": p.status,
            "removed_at": p.removed_at,
        }
        for p in props
    ]


def _biggest_drops(db: Session, region_id: int, limit: int) -> list:
    """降价榜：取 price_history 首尾价差最大的在售房源。"""
    props = (
        db.query(Property)
        .join(RegionProperty, RegionProperty.property_id == Property.id)
        .filter(
            RegionProperty.region_id == region_id,
            Property.status.in_(("listed", "under_offer")),
            Property.current_price.isnot(None),
        )
        .all()
    )
    histories: dict[int, list[PriceHistory]] = {}
    if props:
        rows = (
            db.query(PriceHistory)
            .filter(PriceHistory.property_id.in_([p.id for p in props]))
            .order_by(PriceHistory.captured_at.asc())
            .all()
        )
        for h in rows:
            histories.setdefault(h.property_id, []).append(h)

    rows = []
    for p in props:
        hist = histories.get(p.id, [])
        if len(hist) < 2:
            continue
        first_price = hist[0].price
        current = p.current_price
        if first_price and current and current < first_price:
            rows.append(
                {
                    "id": p.id,
                    "listing_id": p.listing_id,
                    "address": p.address,
                    "bedrooms": p.bedrooms,
                    "property_type": p.property_type,
                    "image_url": p.image_url,
                    "current_price": current,
                    "first_price": first_price,
                    "drop_amount": first_price - current,
                    "drop_pct": round((first_price - current) / first_price * 100, 1),
                }
            )
    rows.sort(key=lambda r: r["drop_amount"], reverse=True)
    return rows[:limit]


def classification(db: Session, region_id: int) -> dict:
    """按类型 / 价格区间 / 状态分组。价格区间基于区域自身分布自适应。"""
    props = (
        db.query(Property)
        .join(RegionProperty, RegionProperty.property_id == Property.id)
        .filter(RegionProperty.region_id == region_id)
        .all()
    )
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    prices = [p.current_price for p in props if p.current_price is not None]
    by_band = _price_bands(prices)

    for p in props:
        t = (p.property_type or "other").lower()
        by_type[t] = by_type.get(t, 0) + 1
        by_status[p.status] = by_status.get(p.status, 0) + 1

    # 归一化类型为三类：房子/公寓/其他
    grouped = {"house": 0, "flat": 0, "other": 0}
    for t, n in by_type.items():
        if "flat" in t or "apartment" in t or "maisonette" in t:
            grouped["flat"] += n
        elif "house" in t or "bungalow" in t:
            grouped["house"] += n
        else:
            grouped["other"] += n

    return {
        "by_type": grouped,
        "by_status": by_status,
        "price_bands": by_band,
    }


def _price_bands(prices: list[int], n_bands: int = 5) -> list[dict]:
    """基于区域自身价格分布的自适应分档（分位数）。"""
    if not prices:
        return []
    prices_sorted = sorted(prices)
    n = len(prices_sorted)
    lo = prices_sorted[0]
    hi = prices_sorted[-1]
    if lo == hi:
        return [{"label": f"£{lo/1000:.0f}k", "min": lo, "max": hi, "count": n}]
    step = (hi - lo) / n_bands
    bands = []
    for i in range(n_bands):
        bmin = lo + step * i
        bmax = lo + step * (i + 1) if i < n_bands - 1 else hi + 1
        count = sum(1 for p in prices if bmin <= p < bmax)
        bands.append(
            {
                "label": f"£{bmin/1000:.0f}k-{bmax/1000:.0f}k",
                "min": int(bmin),
                "max": int(bmax),
                "count": count,
            }
        )
    return bands


def global_search(db: Session, q: str, limit: int = 30) -> list:
    like = f"%{q}%"
    props = (
        db.query(Property)
        .filter(
            or_(
                Property.address.ilike(like),
                Property.postcode.ilike(like),
                Property.town.ilike(like),
            )
        )
        .order_by(Property.current_price.desc())
        .limit(limit * 2)
        .all()
    )
    # 活跃房源优先（listed 最前），其余按价格
    status_rank = {"listed": 0, "under_offer": 1, "sold": 2, "removed": 3}
    props.sort(key=lambda p: status_rank.get(p.status, 9))
    props = props[:limit]

    region_rows = (
        db.query(RegionProperty.property_id, Region.id, Region.name)
        .join(Region, Region.id == RegionProperty.region_id)
        .filter(RegionProperty.property_id.in_([p.id for p in props]))
        .all()
    )
    region_map: dict[int, list[dict]] = {}
    for pid, rid, rname in region_rows:
        region_map.setdefault(pid, []).append({"id": rid, "name": rname})

    return [
        {
            "id": p.id,
            "listing_id": p.listing_id,
            "address": p.address,
            "price": p.current_price,
            "bedrooms": p.bedrooms,
            "property_type": p.property_type,
            "image_url": p.image_url,
            "status": p.status,
            "town": p.town,
            "postcode": p.postcode,
            "regions": region_map.get(p.id, []),
        }
        for p in props
    ]


def region_map(db: Session, region_id: int) -> dict:
    region = db.get(Region, region_id)
    points = (
        db.query(Property)
        .join(RegionProperty, RegionProperty.property_id == Property.id)
        .filter(RegionProperty.region_id == region_id)
        .all()
    )
    return {
        "region_id": region_id,
        "center_lat": region.center_lat if region else None,
        "center_lng": region.center_lng if region else None,
        "radius_km": region.radius_km if region else 0,
        "points": [
            {
                "id": p.id,
                "listing_id": p.listing_id,
                "lat": p.lat,
                "lng": p.lng,
                "price": p.current_price,
                "status": p.status,
                "address": p.address,
            }
            for p in points
        ],
    }


def recent_sync_runs(db: Session, limit: int = 20, region_id: int | None = None) -> list:
    q = db.query(SyncRun).order_by(SyncRun.started_at.desc())
    if region_id is not None:
        q = q.filter(SyncRun.region_id == region_id)
    return q.limit(limit).all()
