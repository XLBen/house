from app.scraper.area import (
    extract_area_from_features,
    extract_area_from_text,
)


def test_sqft_formats():
    assert extract_area_from_text("1,500 sq ft") == 1500
    assert extract_area_from_text("1900 sqft") == 1900
    assert extract_area_from_text("592 sq ft") == 592
    assert extract_area_from_text("936sq.ft") == 936
    assert extract_area_from_text("Extending to approximately 1,500 sq. ft.") == 1500


def test_over_lower_bound():
    assert extract_area_from_text("Over 1,500 sq ft") == 1500


def test_sqm_conversion():
    # 139 sq m ≈ 1496 sq ft
    assert extract_area_from_text("139 sq m") == round(139 * 10.7639104)
    assert extract_area_from_text("100 m2") == round(100 * 10.7639104)


def test_plausibility_guard():
    # 离群值 / 开发整体规模 → None
    assert extract_area_from_text("50 sq ft") is None          # 太小
    assert extract_area_from_text("50,000 sq ft") is None      # 太大
    assert extract_area_from_text("over two million sq ft of workspace") is None


def test_no_area_returns_none():
    assert extract_area_from_text("Stunning Home, Three Bedrooms") is None
    assert extract_area_from_text(None) is None
    assert extract_area_from_text("") is None


def test_multiple_mentions_takes_largest():
    # 套内总面积 vs 局部面积 → 取最大合理值
    assert extract_area_from_text(
        "Total 1,500 sq ft, including 200 sq ft terrace"
    ) == 1500


def test_features_extraction():
    features = [{"id": 2, "feature": "Stunning Home"}, {"id": 3, "feature": "Over 1,500 sq ft"}]
    assert extract_area_from_features(features) == 1500
    assert extract_area_from_features([{"feature": "High Ceilings"}]) is None
    assert extract_area_from_features(None) is None
