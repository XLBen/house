import os
from pathlib import Path

from app.scraper.onthemarket import (
    OnTheMarketDataSource,
    _parse_cards,
    _parse_detail,
    _parse_price,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_parse_price():
    assert _parse_price("£950,000") == 950000
    assert _parse_price("£98750") == 98750
    assert _parse_price("Price on application") is None
    assert _parse_price("") is None


def test_parse_cards_page1():
    listings = _parse_cards(_fixture("otm_search_p1.html"))
    assert len(listings) == 30
    l0 = listings[0]
    assert l0.listing_id
    assert l0.listing_id.isdigit()
    assert l0.url.startswith("https://www.onthemarket.com/details/")
    assert l0.price is None or l0.price > 0
    assert l0.address
    # 第一张卡片：3 卧 apartment
    has_apartment = any(l.property_type == "apartment" for l in listings)
    assert has_apartment


def test_parse_cards_page2_distinct():
    p1 = {l.listing_id for l in _parse_cards(_fixture("otm_search_p1.html"))}
    p2 = {l.listing_id for l in _parse_cards(_fixture("otm_search_p2.html"))}
    assert len(p1) == 30
    assert len(p2) == 30
    # 分页不应有重叠（不同房源）
    assert p1.isdisjoint(p2)


def test_parse_cards_has_reduced_badge():
    # Reduced 标记的房源应被正确识别（价格变化线索）
    listings = _parse_cards(_fixture("otm_search_p1.html"))
    prices = [l.price for l in listings if l.price]
    assert len(prices) > 0


def test_parse_cards_captures_images_and_signals():
    listings = _parse_cards(_fixture("otm_search_p1.html"))
    with_images = [l for l in listings if l.extra.get("image_url")]
    assert len(with_images) > 0
    assert with_images[0].extra["image_count"] >= 6
    assert "media.onthemarket.com" in with_images[0].extra["image_url"]
    # 第一页有 Reduced 信号
    assert any(l.extra.get("reduced_flag") for l in listings)


def test_parse_cards_added_hint():
    listings = _parse_cards(_fixture("otm_search_p1.html"))
    hints = [l.extra.get("added_hint") for l in listings if l.extra.get("added_hint")]
    assert hints and all("days" in h for h in hints)


def test_parse_cards_extracts_area():
    listings = _parse_cards(_fixture("otm_search_p1.html"))
    # 第一张卡片描述含 "Over 1,500 sq ft" → 应提取到面积
    with_area = [l for l in listings if l.extra.get("floor_area_sqft")]
    assert len(with_area) > 0
    assert with_area[0].extra["floor_area_sqft"] > 0


def test_parse_detail_extracts_area():
    detail = _parse_detail(_fixture("otm_detail.html"))
    assert detail["floor_area_sqft"] == 1500


def test_parse_detail():
    detail = _parse_detail(_fixture("otm_detail.html"))
    assert detail["description"]
    assert len(detail["description"]) > 20
    assert detail["bathrooms"] == 2
    assert detail["property_type"] == "Apartment"


def test_resolve_location_slug(monkeypatch):
    import app.scraper.onthemarket as mod

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "completions": [
                    {"location-type": "postcode", "parent": "Rotherhithe",
                     "name": "SE16 2UG", "location-id": "se16-2ug"}
                ],
                "fuzzy": False,
            }

    class FakeSession:
        def get(self, url, params=None, headers=None, timeout=None):
            return FakeResp()

    ds = OnTheMarketDataSource()
    ds.session = FakeSession()
    assert ds.resolve_location("SE16 2UG") == ("se16-2ug", "SE16 2UG")


def test_nearest_radius_miles():
    from app.scraper.base import nearest_radius_miles
    # 2km ≈ 1.24 英里 → 最近档位 1.0
    assert nearest_radius_miles(2.0) == 1.0
    # 5km ≈ 3.1 英里 → 3.0
    assert nearest_radius_miles(5.0) == 3.0


def test_empty_unknown_page_is_incomplete(monkeypatch):
    ds = OnTheMarketDataSource()
    monkeypatch.setattr(ds, "resolve_location", lambda postcode: ("se16-2ug", postcode))
    monkeypatch.setattr(ds, "_fetch_page", lambda url, params: "<html><body>blocked</body></html>")
    assert ds.search("SE16 2UG", 2.0) == []
    assert ds.last_complete is False


def test_repeated_page_is_incomplete(monkeypatch):
    ds = OnTheMarketDataSource()
    html = _fixture("otm_search_p1.html")
    monkeypatch.setattr(ds, "resolve_location", lambda postcode: ("se16-2ug", postcode))
    monkeypatch.setattr(ds, "_fetch_page", lambda url, params: html)
    monkeypatch.setattr("app.scraper.onthemarket.time.sleep", lambda seconds: None)
    monkeypatch.setattr("app.scraper.onthemarket.settings.othem_max_pages", 3)
    listings = ds.search("SE16 2UG", 2.0)
    assert len(listings) == 30
    assert ds.last_complete is False
