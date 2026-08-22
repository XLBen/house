"""API 层测试：验证路由薄层 + service 契约（此前完全没有 API 测试）。"""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.scraper.mock import MockDataSource
from app.services.sync_service import sync_region

client = TestClient(app)


def _seed_region(db):
    from app.models import Region

    region = Region(
        name="Bermondsey",
        center_postcode="SE16 2UG",
        radius_km=2.0,
        is_active=True,
    )
    db.add(region)
    db.commit()
    db.refresh(region)
    sync_region(db, region, MockDataSource(today=date(2026, 1, 1)))
    return region.id


def test_list_regions_empty(db):
    res = client.get("/api/regions")
    assert res.status_code == 200
    assert res.json() == []


def test_create_region_mock_offline(db):
    res = client.post(
        "/api/regions",
        json={"name": "Test", "center_postcode": "LS1 1AA", "radius_km": 1.0},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Test"
    assert data["stats"] is not None
    # mock 模式下应能拿到确定性坐标（无需联网）
    assert data["center_lat"] is not None


def test_region_stats_and_properties(db):
    region_id = _seed_region(db)
    stats = client.get(f"/api/regions/{region_id}/stats")
    assert stats.status_code == 200
    body = stats.json()
    assert body["region_id"] == region_id
    assert body["active_count"] > 0
    assert "median_price" in body
    assert "biggest_drops" in body

    props = client.get(f"/api/regions/{region_id}/properties")
    assert props.status_code == 200
    pbody = props.json()
    assert pbody["total"] > 0
    assert pbody["items"][0]["listing_id"]


def test_region_stats_404(db):
    res = client.get("/api/regions/9999/stats")
    assert res.status_code == 404


def test_property_detail_and_history(db):
    region_id = _seed_region(db)
    pid = client.get(f"/api/regions/{region_id}/properties").json()["items"][0]["id"]
    detail = client.get(f"/api/properties/{pid}")
    assert detail.status_code == 200
    dbody = detail.json()
    assert dbody["price_history"]  # 详情内含价格历史
    assert "first_price" in dbody


def test_changes_first_sync(db):
    region_id = _seed_region(db)
    res = client.get(f"/api/regions/{region_id}/changes?since=last_sync")
    assert res.status_code == 200
    body = res.json()
    assert body["is_first_sync"] is True
    assert len(body["new"]) > 0


def test_watch_flow(db):
    region_id = _seed_region(db)
    pid = client.get(f"/api/regions/{region_id}/properties").json()["items"][0]["id"]

    check = client.get(f"/api/watch/check/{pid}")
    assert check.json() == {"watched": False}

    add = client.post(f"/api/watch/{pid}")
    assert add.status_code == 200
    assert add.json() == {"watched": True}

    wl = client.get("/api/watchlist")
    assert wl.status_code == 200
    assert any(w["id"] == pid for w in wl.json())

    remove = client.delete(f"/api/watch/{pid}")
    assert remove.status_code == 204
    assert client.get(f"/api/watch/check/{pid}").json() == {"watched": False}


def test_watch_add_unknown_property_404(db):
    res = client.post("/api/watch/99999")
    assert res.status_code == 404


def test_search(db):
    region_id = _seed_region(db)
    res = client.get("/api/search", params={"q": "SE16"})
    assert res.status_code == 200
    results = res.json()
    assert len(results) > 0
    assert any(r["regions"] for r in results)


def test_classification_and_map(db):
    region_id = _seed_region(db)
    cls = client.get(f"/api/regions/{region_id}/classification")
    assert cls.status_code == 200
    cbody = cls.json()
    assert set(cbody["by_type"]) == {"house", "flat", "other"}

    mp = client.get(f"/api/regions/{region_id}/map")
    assert mp.status_code == 200
    assert mp.json()["radius_km"] == 2.0


def test_sync_runs_endpoint(db):
    region_id = _seed_region(db)
    res = client.get("/api/sync/runs")
    assert res.status_code == 200
    runs = res.json()
    assert runs[0]["region_id"] == region_id
    assert "price_changed_count" in runs[0]
    assert "status_changed_count" in runs[0]


def test_export_all(db):
    region_id = _seed_region(db)
    res = client.get("/api/export/all")
    assert res.status_code == 200
    body = res.json()
    assert body["regions"]
    assert body["properties"]
    assert "sync_runs" in body
