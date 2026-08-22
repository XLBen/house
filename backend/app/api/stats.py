"""统计 / 分类 / 搜索 / 收藏 / 同步日志 API（薄层）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models import Property, Region
from ..schemas.region import SyncRunOut
from ..schemas.stats import RegionMapOut, RegionStatsOut
from ..services import sync_service, watch_service
from ..services.change_service import (
    classification,
    global_search,
    recent_sync_runs,
    region_map,
    region_stats,
)

router = APIRouter(tags=["stats"])


def _get_region(db: Session, region_id: int) -> Region:
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="区域不存在")
    return region


@router.get("/api/regions/{region_id}/stats", response_model=RegionStatsOut)
def stats(region_id: int, db: Session = Depends(get_db)):
    _get_region(db, region_id)
    return region_stats(db, region_id)


@router.get("/api/regions/{region_id}/map", response_model=RegionMapOut)
def map_data(region_id: int, db: Session = Depends(get_db)):
    _get_region(db, region_id)
    return region_map(db, region_id)


@router.get("/api/regions/{region_id}/classification")
def region_classification(region_id: int, db: Session = Depends(get_db)):
    _get_region(db, region_id)
    return classification(db, region_id)


@router.get("/api/search")
def search(q: str = Query(..., min_length=2), db: Session = Depends(get_db)):
    return global_search(db, q)


@router.get("/api/watchlist")
def watchlist(db: Session = Depends(get_db)):
    return watch_service.watchlist(db)


@router.get("/api/watch/check/{property_id}")
def watch_check(property_id: int, db: Session = Depends(get_db)):
    return {"watched": watch_service.watch_check(db, property_id)}


@router.post("/api/watch/{property_id}")
def watch_add(property_id: int, db: Session = Depends(get_db)):
    if db.get(Property, property_id) is None:
        raise HTTPException(status_code=404, detail="房源不存在")
    watch_service.watch_add(db, property_id)
    return {"watched": True}


@router.delete("/api/watch/{property_id}", status_code=204)
def watch_remove(property_id: int, db: Session = Depends(get_db)):
    watch_service.watch_remove(db, property_id)


@router.get("/api/export/all")
def export_all(db: Session = Depends(get_db)):
    return watch_service.export_all_json(db)


@router.get("/api/sync/runs", response_model=list[SyncRunOut])
def sync_runs(
    region_id: int | None = Query(None),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    runs = recent_sync_runs(db, limit=limit, region_id=region_id)
    return [SyncRunOut.model_validate(r) for r in runs]


@router.post("/api/sync/all")
def sync_all_now(db: Session = Depends(get_db)):
    results = sync_service.sync_all(db)
    return {"results": {str(k): v for k, v in results.items()}}
