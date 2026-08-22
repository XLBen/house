from datetime import date

from app.models import (
    Event,
    PriceHistory,
    Property,
    Region,
    RegionProperty,
    RegionSnapshot,
)
from app.scraper.base import Listing
from app.scraper.mock import MockDataSource
from app.services.sync_service import sync_all, sync_region


def _mk_region(db, name="Test", postcode="LS1 1AA", radius=2.0):
    region = Region(
        name=name, center_postcode=postcode, radius_km=radius, is_active=True
    )
    db.add(region)
    db.commit()
    db.refresh(region)
    return region


def test_first_sync_creates_properties_and_events(db):
    region = _mk_region(db)
    result = sync_region(db, region, MockDataSource(today=date(2026, 1, 1)))
    assert result["new_count"] > 0
    props = db.query(Property).all()
    assert len(props) == result["new_count"]
    for p in props:
        assert db.query(PriceHistory).filter_by(property_id=p.id).count() >= 1
        assert db.query(Event).filter_by(property_id=p.id, event_type="new").count() >= 1
        assert (
            db.query(RegionProperty)
            .filter_by(property_id=p.id, region_id=region.id)
            .count()
            == 1
        )
    snap = db.query(RegionSnapshot).filter_by(region_id=region.id).first()
    assert snap is not None
    assert snap.active_count == len(props)


def test_second_sync_same_day_no_changes(db):
    region = _mk_region(db)
    sync_region(db, region, MockDataSource(today=date(2026, 1, 1)))
    n_history = db.query(PriceHistory).count()
    n_events = db.query(Event).count()
    result = sync_region(db, region, MockDataSource(today=date(2026, 1, 1)))
    # 数据完全一致 -> 无新增、无变化事件、无额外价格历史
    assert result["new_count"] == 0
    assert result["changed_count"] == 0
    assert db.query(PriceHistory).count() == n_history
    assert db.query(Event).count() == n_events


def test_price_change_detected_next_day(db):
    region = _mk_region(db)
    sync_region(db, region, MockDataSource(today=date(2026, 1, 1)))
    n_history = db.query(PriceHistory).count()
    result = sync_region(db, region, MockDataSource(today=date(2026, 1, 2)))
    price_events = (
        db.query(Event).filter_by(event_type="price_change").count()
    )
    # 价格随日期漂移，应当至少有一个价格变化
    assert price_events > 0
    assert db.query(PriceHistory).count() > n_history
    assert result["new_count"] == 0


def test_delisted_requires_grace_period(db):
    """C1：房源连续缺席达到阈值才判消失，避免瞬时抓取问题误删。"""
    region = _mk_region(db)
    sync_region(db, region, MockDataSource(today=date(2026, 1, 1)))

    class EmptySource:
        last_complete = True

        def search(self, postcode, radius_km):
            return []

        def geocode(self, postcode):
            return None

        def close(self):
            pass

    # 第一次缺席：只计数，不判消失
    r1 = sync_region(db, region, EmptySource())
    assert r1["delisted_count"] == 0
    assert db.query(Property).filter(Property.status == "removed").count() == 0
    # 第二次缺席：达到阈值才判消失
    r2 = sync_region(db, region, EmptySource())
    assert r2["delisted_count"] > 0
    assert db.query(Property).filter(Property.status == "removed").count() == r2["delisted_count"]
    for p in db.query(Property).filter(Property.status == "removed").all():
        assert p.removed_at is not None


def test_incomplete_search_skips_delisted(db):
    """C1：搜索不完整（last_complete=False）时，绝不执行消失检测。"""
    region = _mk_region(db)
    sync_region(db, region, MockDataSource(today=date(2026, 1, 1)))

    class PartialSource:
        last_complete = False

        def search(self, postcode, radius_km):
            return []  # 看似空结果，但标记不完整

        def geocode(self, postcode):
            return None

        def close(self):
            pass

    sync_region(db, region, PartialSource())
    sync_region(db, region, PartialSource())
    assert db.query(Property).filter(Property.status == "removed").count() == 0


def test_seen_resets_miss_count(db):
    """C1：房源重新出现后 miss_count 归零。"""
    region = _mk_region(db)
    sync_region(db, region, MockDataSource(today=date(2026, 1, 1)))

    class EmptySource:
        last_complete = True

        def search(self, postcode, radius_km):
            return []

        def geocode(self, postcode):
            return None

        def close(self):
            pass

    sync_region(db, region, EmptySource())  # miss_count = 1
    assert db.query(Property).filter(Property.miss_count >= 1).count() > 0
    # 重新出现 → miss_count 归零
    sync_region(db, region, MockDataSource(today=date(2026, 1, 1)))
    assert db.query(Property).filter(Property.miss_count > 0).count() == 0


def test_relist_merges_by_fingerprint(db):
    """同一物理房子下架后重新挂牌（新 listing_id），应按指纹合并并记录价格变化。"""
    region = _mk_region(db)
    sync_region(db, region, MockDataSource(today=date(2026, 1, 1)))
    prop = db.query(Property).first()
    old_price = prop.current_price
    prop.status = "removed"
    prop.removed_at = date(2026, 1, 1)
    db.commit()

    new_listing = Listing(
        listing_id="9999999",
        url="https://www.rightmove.co.uk/properties/9999999",
        price=(old_price - 25000) if old_price else 100000,
        bedrooms=prop.bedrooms,
        property_type=prop.property_type,
        address=prop.address,
        postcode=prop.postcode,
        street=prop.street,
        number=prop.number,
        description="一个全新的描述文字，应该不影响身份识别",
    )

    class OneSource:
        def search(self, postcode, radius_km):
            return [new_listing]

        def geocode(self, postcode):
            return None

        def close(self):
            pass

    sync_region(db, region, OneSource())

    merged = db.query(Property).filter_by(listing_id="9999999").first()
    assert merged is not None
    # 复用了同一物理记录（不是新建）
    assert merged.id == prop.id
    assert merged.status == "listed"
    # 重挂后 removed_at 清空、relisted_at 记录
    assert merged.removed_at is None
    assert merged.relisted_at is not None
    # 记录了一次价格变化（有意义变化）
    pc = (
        db.query(Event)
        .filter_by(
            property_id=prop.id,
            event_type="price_change",
            old_value=str(old_price),
        )
        .first()
    )
    assert pc is not None


def test_first_sync_flag(db):
    region = _mk_region(db)
    r1 = sync_region(db, region, MockDataSource(today=date(2026, 1, 1)))
    assert r1["is_first_sync"] is True
    r2 = sync_region(db, region, MockDataSource(today=date(2026, 1, 1)))
    assert r2["is_first_sync"] is False


def test_is_first_sync_false_after_second(db):
    """回归：二次同步后 changes 的 is_first_sync 必须为 False（不得永远 True）。"""
    from app.services.change_service import changes_for_region

    region = _mk_region(db)
    sync_region(db, region, MockDataSource(today=date(2026, 1, 1)))
    c1 = changes_for_region(db, region.id, since="last_sync")
    assert c1.is_first_sync is True
    sync_region(db, region, MockDataSource(today=date(2026, 1, 1)))
    c2 = changes_for_region(db, region.id, since="last_sync")
    assert c2.is_first_sync is False


def test_incomplete_search_sets_complete_flag(db):
    region = _mk_region(db)

    class PartialSource:
        last_complete = False

        def search(self, postcode, radius_km):
            return []

        def geocode(self, postcode):
            return None

        def close(self):
            pass

    r = sync_region(db, region, PartialSource())
    assert r["complete"] is False


def test_detail_budget_limits_fetches(db):
    """每次同步详情抓取受预算限制，剩余后续补齐（控制首次同步耗时）。"""
    region = _mk_region(db)

    class BudgetSource:
        last_complete = True
        relist_merge = False
        detail_budget = 3
        calls = 0

        def search(self, postcode, radius_km):
            return [
                Listing(
                    listing_id=str(i), url=f"u{i}", price=100000 + i,
                    bedrooms=1, property_type="flat", address=f"addr {i}",
                )
                for i in range(5)
            ]

        def fetch_detail(self, listing_id):
            self.calls += 1
            return {"description": f"desc {listing_id}"}

        def geocode(self, postcode):
            return None

        def close(self):
            pass

    src = BudgetSource()
    sync_region(db, region, src)
    assert src.calls <= 3
    # 剩余房源后续同步补齐
    src2 = BudgetSource()
    sync_region(db, region, src2)
    assert db.query(Property).filter(Property.description.isnot(None)).count() >= 3


def test_sync_all_reuses_search_for_duplicate_regions(db, monkeypatch):
    first = _mk_region(db, name="Same 1")
    second = _mk_region(db, name="Same 2")

    class CountingSource(MockDataSource):
        name = "mock"
        calls = 0

        def search(self, postcode, radius_km):
            self.calls += 1
            return super().search(postcode, radius_km)

    source = CountingSource(today=date(2026, 1, 1))
    monkeypatch.setattr("app.services.sync_service.get_data_source", lambda name: source)
    results = sync_all(db)
    assert set(results) == {first.id, second.id}
    assert source.calls == 1


def test_sync_run_records_source(db):
    from app.models import SyncRun

    region = _mk_region(db)
    sync_region(db, region, MockDataSource(today=date(2026, 1, 1)))
    run = db.query(SyncRun).filter_by(region_id=region.id).one()
    assert run.data_source == "mock"


def test_duplicate_listing_in_one_result_does_not_duplicate_membership(db):
    region = _mk_region(db)
    listing = Listing(
        listing_id="duplicate-1",
        url="https://example.test/duplicate-1",
        price=250000,
        address="1 Test Street",
    )

    class DuplicateSource:
        name = "test"
        last_complete = True

        def search(self, postcode, radius_km):
            return [listing, listing]

        def geocode(self, postcode):
            return None

        def close(self):
            pass

    result = sync_region(db, region, DuplicateSource())
    assert result["error"] is None
    assert db.query(RegionProperty).filter_by(region_id=region.id).count() == 1


def test_notify_noop_without_config(db):
    """未配置通知时，notify 静默跳过（不发网络请求、不抛错）。"""
    from app.services.notify import notify_region_sync

    region = _mk_region(db)
    result = {"new_count": 1, "delisted_count": 0, "changed_count": 0, "error": None}
    notify_region_sync(db, region, result)  # 默认无 webhook/telegram → no-op


def test_delisted_sets_removed_at(db):
    region = _mk_region(db)
    sync_region(db, region, MockDataSource(today=date(2026, 1, 1)))

    class EmptySource:
        last_complete = True

        def search(self, postcode, radius_km):
            return []

        def geocode(self, postcode):
            return None

        def close(self):
            pass

    # 需连续缺席两次达到宽限期
    sync_region(db, region, EmptySource())
    sync_region(db, region, EmptySource())
    removed = db.query(Property).filter(Property.status == "removed").all()
    assert len(removed) > 0
    for p in removed:
        assert p.removed_at is not None
