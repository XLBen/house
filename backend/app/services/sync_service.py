"""同步服务：核心编排。

流程（对每个活跃区域）：
1. 从数据源搜索该区域的房源；
2. 按 listing_id upsert；新 ID 先算物理指纹，若匹配到已下架的同一套房子则"合并"（复用记录、链接历史）；
3. 价格变化 → 写 price_history + price_change 事件（有意义变化）；状态变化 → status_change 事件；
4. 描述/其他字段 → 仅刷新，不产生事件；
5. 本次搜索中消失的房源 → 标记 removed + delisted 事件；
6. 维护区域成员关系 + 每日快照；记录 SyncRun 日志。
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime

from sqlalchemy.orm import Session

from ..core.config import settings
from ..identity.fingerprint import build_fingerprint
from ..models import (
    Event,
    PriceHistory,
    Property,
    Region,
    RegionProperty,
    RegionSnapshot,
    SyncRun,
)
from ..scraper.base import BaseDataSource, Listing, get_data_source
from .change_service import is_first_sync
from .dates import day_bounds, now_utc, utc_today

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = ("listed", "under_offer", "sold")

# 同一进程内串行化同步，避免 0 点任务与手动同步并发双写（M2）
_SYNC_LOCK = threading.Lock()

# 可能被 _fill_detail / 状态字段写为"非挂牌"的状态，参与变化统计
_PRICE_KIND = "price"
_STATUS_KIND = "status"


def _record_event(
    db: Session,
    *,
    property_id: int,
    region_id: int | None,
    event_type: str,
    old_value: str | None = None,
    new_value: str | None = None,
    occurred_at: datetime | None = None,
) -> None:
    db.add(
        Event(
            property_id=property_id,
            region_id=region_id,
            event_type=event_type,
            old_value=old_value,
            new_value=new_value,
            occurred_at=occurred_at or now_utc(),
        )
    )


def sync_all(db: Session) -> dict:
    """同步所有活跃区域。返回 {region_id: result}。"""
    source = get_data_source(settings.data_source)
    try:
        results: dict = {}
        regions = db.query(Region).filter(Region.is_active.is_(True)).all()
        # 相同邮编和半径的区域共享一次网络搜索，避免重复请求触发限流。
        search_cache: dict[tuple[str, float], tuple[list[Listing], bool]] = {}
        with _SYNC_LOCK:
            for region in regions:
                results[region.id] = _sync_region_locked(
                    db, region, source, search_cache=search_cache
                )
        return results
    finally:
        source.close()


def sync_region(db: Session, region: Region, source: BaseDataSource | None = None) -> dict:
    with _SYNC_LOCK:
        return _sync_region_locked(db, region, source)


def _sync_region_locked(
    db: Session,
    region: Region,
    source: BaseDataSource | None = None,
    *,
    search_cache: dict[tuple[str, float], tuple[list[Listing], bool]] | None = None,
) -> dict:
    source = source or get_data_source(settings.data_source)
    started = now_utc()
    region_id = region.id
    region_name = region.name
    run = SyncRun(
        region_id=region_id,
        started_at=started,
        status="running",
        data_source=_source_name(source),
    )
    db.add(run)
    db.commit()
    result = {
        "region_id": region.id,
        "new_count": 0,
        "changed_count": 0,
        "price_changed_count": 0,
        "status_changed_count": 0,
        "delisted_count": 0,
        "is_first_sync": False,
        "complete": True,
        "error": None,
    }
    # 每次同步的详情抓取预算（控制首次同步耗时，剩余后续补齐）
    if getattr(source, "detail_budget", None) is None:
        source.detail_budget = settings.othem_detail_per_sync
    pending_memberships: set[tuple[int, int]] = set()
    try:
        search_key = (region.center_postcode, region.radius_km)
        if search_cache is not None and search_key in search_cache:
            listings, search_complete = search_cache[search_key]
        else:
            listings = source.search(region.center_postcode, region.radius_km)
            search_complete = getattr(source, "last_complete", True)
            if search_cache is not None:
                search_cache[search_key] = (listings, search_complete)
        result["complete"] = search_complete
        seen_ids: set[str] = set()
        for li in listings:
            seen_ids.add(li.listing_id)
            prop = (
                db.query(Property)
                .filter(
                    Property.listing_id == li.listing_id,
                    Property.data_source == _source_name(source),
                )
                .first()
            )
            if prop is None:
                collision = (
                    db.query(Property)
                    .filter(Property.listing_id == li.listing_id)
                    .first()
                )
                if collision is not None:
                    raise ValueError(
                        "数据源挂牌 ID 冲突: "
                        f"{li.listing_id} ({collision.data_source} vs {_source_name(source)})"
                    )
                prop, kind = _create_property(db, region, li, source)
                if prop is not None:
                    result["new_count"] += 1
                    if kind:
                        _apply_change_kind(result, kind)
            else:
                kind = _update_property(db, region, prop, li, source)
                if kind:
                    _apply_change_kind(result, kind)
            if prop is not None:
                _ensure_membership(db, region, prop, pending_memberships)
                prop.last_seen_at = started
                if prop.status in _ACTIVE_STATUSES:
                    prop.miss_count = 0

        db.flush()

        # 只有搜索完整时才允许判定"消失"（C1 防部分结果误删）
        if search_complete:
            result["delisted_count"] = _detect_delistings(
                db, region, seen_ids, started
            )
        else:
            logger.warning(
                "区域 %s 本次搜索不完整，跳过消失检测（现有房源不判下架）",
                region_name,
            )

        region.last_synced_at = started
        _write_snapshot(db, region)
        run.status = "success"
        run.complete = search_complete
        run.new_count = result["new_count"]
        run.changed_count = result["changed_count"]
        run.price_changed_count = result["price_changed_count"]
        run.status_changed_count = result["status_changed_count"]
        run.delisted_count = result["delisted_count"]
        logger.info(
            "区域 %s 同步完成: 新增 %d, 调价 %d, 状态变化 %d, 下架 %d",
            region.name,
            result["new_count"],
            result["price_changed_count"],
            result["status_changed_count"],
            result["delisted_count"],
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("区域 %s 同步失败", region_name)
        # 不提交本次失败前已经写入的半成品，只保留一条 error SyncRun。
        db.rollback()
        run = SyncRun(
            region_id=region_id,
            started_at=started,
            status="error",
            data_source=_source_name(source),
        )
        run.status = "error"
        run.error = str(exc)[:2000]
        result["error"] = str(exc)
        result["complete"] = False
    finally:
        run.finished_at = now_utc()
        db.add(run)
        db.commit()
    if result.get("error") is None:
        result["is_first_sync"] = is_first_sync(db, region_id)
        try:
            from .notify import notify_region_sync

            notify_region_sync(db, region, result)
        except Exception as exc:  # noqa: BLE001
            logger.debug("通知失败: %s", exc)
    return result


def _apply_change_kind(result: dict, kind: str) -> None:
    result["changed_count"] += 1
    if kind == _PRICE_KIND:
        result["price_changed_count"] += 1
    elif kind == _STATUS_KIND:
        result["status_changed_count"] += 1


def _create_property(
    db: Session, region: Region, li: Listing, source: BaseDataSource
) -> tuple[Property | None, str | None]:
    """创建新房源；若指纹命中已下架房源则走合并。返回 (prop, 变化类型)。"""
    fp = build_fingerprint(
        li.postcode, li.street, li.address, li.bedrooms, li.property_type
    )
    # 物理身份合并：同指纹且已下架的旧房源 = 同一套房子重新挂牌。
    # 仅当数据源指纹可靠（relist_merge=True）时启用；OTM 无门牌/邮编 → 关闭。
    existing = None
    if getattr(source, "relist_merge", True):
        existing = (
            db.query(Property)
            .filter(
                Property.fingerprint == fp,
                Property.listing_id != li.listing_id,
                Property.status == "removed",
            )
            .first()
        )
    if existing is not None:
        return _merge_relisted(db, region, existing, li, fp)

    prop = Property(
        listing_id=li.listing_id,
        data_source=_source_name(source),
        fingerprint=fp,
        status=li.status or "listed",
        current_price=li.price,
        first_seen_at=now_utc(),
        last_seen_at=now_utc(),
    )
    _apply_listing_fields(prop, li)
    db.add(prop)
    db.flush()
    if li.price is not None:
        db.add(PriceHistory(property_id=prop.id, price=li.price, captured_at=now_utc()))
    _record_event(
        db,
        property_id=prop.id,
        region_id=region.id,
        event_type="new",
        new_value=str(li.price) if li.price is not None else None,
    )
    _fill_detail(db, region, prop, source)
    return prop, None


def _merge_relisted(
    db: Session, region: Region, prop: Property, li: Listing, fp: str
) -> tuple[Property, str | None]:
    """重新挂牌的同一套房子：复用记录，更新 listing_id，对比价格产生事件。"""
    old_price = prop.current_price
    prop.listing_id = li.listing_id
    prop.fingerprint = fp
    prop.status = li.status or "listed"
    prop.removed_at = None
    prop.relisted_at = now_utc()
    prop.miss_count = 0
    _apply_listing_fields(prop, li)
    kind = None
    if (
        old_price is not None
        and li.price is not None
        and li.price != old_price
    ):
        db.add(PriceHistory(property_id=prop.id, price=li.price, captured_at=now_utc()))
        _record_event(
            db,
            property_id=prop.id,
            region_id=region.id,
            event_type="price_change",
            old_value=str(old_price),
            new_value=str(li.price),
        )
        kind = _PRICE_KIND
    elif old_price is None and li.price is not None:
        db.add(PriceHistory(property_id=prop.id, price=li.price, captured_at=now_utc()))
    _record_event(
        db,
        property_id=prop.id,
        region_id=region.id,
        event_type="new",
        old_value="relisted",
        new_value=str(li.price) if li.price is not None else None,
    )
    db.flush()
    return prop, kind


def _update_property(
    db: Session, region: Region, prop: Property, li: Listing, source: BaseDataSource
) -> str | None:
    """更新已有房源。返回变化类型：'price' / 'status' / None。"""
    old_price = prop.current_price
    old_status = prop.status
    _apply_listing_fields(prop, li)
    kind = None

    if li.price is not None and old_price is not None and li.price != old_price:
        db.add(PriceHistory(property_id=prop.id, price=li.price, captured_at=now_utc()))
        _record_event(
            db,
            property_id=prop.id,
            region_id=region.id,
            event_type="price_change",
            old_value=str(old_price),
            new_value=str(li.price),
        )
        kind = _PRICE_KIND
    elif old_price is None and li.price is not None:
        db.add(PriceHistory(property_id=prop.id, price=li.price, captured_at=now_utc()))

    new_status = li.status or "listed"
    if new_status != old_status:
        _record_event(
            db,
            property_id=prop.id,
            region_id=region.id,
            event_type="status_change",
            old_value=old_status,
            new_value=new_status,
        )
        kind = _STATUS_KIND if kind is None else kind
    prop.status = new_status
    prop.current_price = li.price
    # 缺描述时补抓详情（受预算限制，不会拖慢同步）
    if prop.description is None and li.description is None:
        _fill_detail(db, region, prop, source)
    return kind


def _apply_listing_fields(prop: Property, li: Listing) -> None:
    prop.address = li.address or prop.address
    prop.postcode = li.postcode or prop.postcode
    prop.number = li.number or prop.number
    prop.street = li.street or prop.street
    prop.locality = li.locality or prop.locality
    prop.town = li.town or prop.town
    prop.bedrooms = li.bedrooms if li.bedrooms is not None else prop.bedrooms
    prop.bathrooms = li.bathrooms if li.bathrooms is not None else prop.bathrooms
    prop.property_type = li.property_type or prop.property_type
    prop.lat = li.lat if li.lat is not None else prop.lat
    prop.lng = li.lng if li.lng is not None else prop.lng
    prop.url = li.url or prop.url
    if li.description:
        prop.description = li.description
    if li.extra:
        for key in ("image_url", "image_count", "reduced_flag", "new_home_flag", "added_hint", "floor_area_sqft"):
            if key in li.extra and li.extra[key] is not None:
                setattr(prop, key, li.extra[key])


def _source_name(source: BaseDataSource) -> str:
    return getattr(source, "name", None) or settings.data_source


def _fill_detail(db: Session, region: Region, prop: Property, source: BaseDataSource) -> None:
    fetch = getattr(source, "fetch_detail", None)
    if fetch is None:
        return
    # 每次同步的详情抓取预算：达到上限则本轮跳过，后续同步补齐
    budget = getattr(source, "detail_budget", None)
    if budget is not None:
        if budget <= 0:
            return
        source.detail_budget -= 1
    try:
        detail = fetch(prop.listing_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("fetch_detail %s failed: %s", prop.listing_id, exc)
        return
    if not detail:
        return
    if detail.get("description") and not prop.description:
        prop.description = detail["description"]
    if detail.get("bathrooms") is not None and prop.bathrooms is None:
        prop.bathrooms = detail["bathrooms"]
    if detail.get("property_type") and not prop.property_type:
        prop.property_type = detail["property_type"]
    if detail.get("floor_area_sqft") is not None and prop.floor_area_sqft is None:
        prop.floor_area_sqft = detail["floor_area_sqft"]
    old_status = prop.status
    if detail.get("status") and detail["status"] != "listed" and old_status == "listed":
        prop.status = detail["status"]
        # 状态变化必须记事件（此前被遗漏的漏洞）
        _record_event(
            db,
            property_id=prop.id,
            region_id=region.id,
            event_type="status_change",
            old_value=old_status,
            new_value=detail["status"],
        )


def _ensure_membership(
    db: Session,
    region: Region,
    prop: Property,
    pending: set[tuple[int, int]] | None = None,
) -> None:
    key = (region.id, prop.id)
    if pending is not None and key in pending:
        return
    exists = (
        db.query(RegionProperty)
        .filter(
            RegionProperty.region_id == region.id,
            RegionProperty.property_id == prop.id,
        )
        .first()
    )
    if exists is None:
        if pending is not None:
            pending.add(key)
        db.add(
            RegionProperty(
                region_id=region.id, property_id=prop.id, added_at=now_utc()
            )
        )


def _detect_delistings(
    db: Session, region: Region, seen_ids: set[str], started: datetime
) -> int:
    """宽限期消失检测：连续缺席达阈值才判下架（防瞬时抓取问题误删）。"""
    members = (
        db.query(Property)
        .join(RegionProperty, RegionProperty.property_id == Property.id)
        .filter(
            RegionProperty.region_id == region.id,
            Property.status.in_(_ACTIVE_STATUSES),
        )
        .all()
    )
    delisted = 0
    for prop in members:
        if prop.listing_id not in seen_ids:
            prop.miss_count += 1
            if prop.miss_count >= settings.miss_threshold:
                _mark_delisted(db, region, prop, started)
                delisted += 1
    return delisted


def _mark_delisted(db: Session, region: Region, prop: Property, at: datetime) -> None:
    old_status = prop.status
    prop.status = "removed"
    prop.removed_at = at
    prop.last_seen_at = at
    _record_event(
        db,
        property_id=prop.id,
        region_id=region.id,
        event_type="delisted",
        old_value=old_status,
        new_value="removed",
        occurred_at=at,
    )


def _write_snapshot(db: Session, region: Region) -> None:
    today = utc_today()
    start, end = day_bounds(today)
    members = (
        db.query(Property)
        .join(RegionProperty, RegionProperty.property_id == Property.id)
        .filter(
            RegionProperty.region_id == region.id,
            Property.status.in_(_ACTIVE_STATUSES),
        )
        .all()
    )
    prices = sorted(p.current_price for p in members if p.current_price is not None)
    snapshot = (
        db.query(RegionSnapshot)
        .filter(RegionSnapshot.region_id == region.id, RegionSnapshot.date == today)
        .first()
    )
    if snapshot is None:
        snapshot = RegionSnapshot(region_id=region.id, date=today)
        db.add(snapshot)
    snapshot.active_count = len(members)
    snapshot.avg_price = round(sum(prices) / len(prices), 2) if prices else None
    snapshot.median_price = _median(prices)
    snapshot.min_price = prices[0] if prices else None
    snapshot.max_price = prices[-1] if prices else None
    snapshot.new_count = _count_events(db, region.id, "new", start, end)
    snapshot.price_change_count = _count_events(db, region.id, "price_change", start, end)
    snapshot.delisted_count = _count_events(db, region.id, "delisted", start, end)


def _median(values: list[int]) -> float | None:
    if not values:
        return None
    n = len(values)
    mid = n // 2
    if n % 2 == 1:
        return float(values[mid])
    return (values[mid - 1] + values[mid]) / 2.0


def _count_events(
    db: Session, region_id: int, event_type: str, start: datetime, end: datetime
) -> int:
    return (
        db.query(Event)
        .filter(
            Event.region_id == region_id,
            Event.event_type == event_type,
            Event.occurred_at >= start,
            Event.occurred_at <= end,
        )
        .count()
    )
