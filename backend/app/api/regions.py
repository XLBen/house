"""区域 CRUD API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models import Region, SyncRun
from ..schemas.region import RegionCreate, RegionOut, RegionUpdate, SyncRunOut
from ..schemas.stats import RegionStatsOut
from ..services import region_service, sync_service
from ..services.change_service import region_stats_light

router = APIRouter(prefix="/api/regions", tags=["regions"])


def _get_region(db: Session, region_id: int) -> Region:
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="区域不存在")
    return region


def _latest_syncs(db: Session, region_ids: list[int]) -> dict[int, SyncRun]:
    if not region_ids:
        return {}
    rows = (
        db.query(SyncRun)
        .filter(SyncRun.region_id.in_(region_ids))
        .order_by(SyncRun.started_at.desc())
        .all()
    )
    latest: dict[int, SyncRun] = {}
    for run in rows:
        latest.setdefault(run.region_id, run)
    return latest


def _region_out(db: Session, region: Region) -> RegionOut:
    out = RegionOut.model_validate(region)
    out.stats = RegionStatsOut(**region_stats_light(db, region.id))
    last_sync = _latest_syncs(db, [region.id]).get(region.id)
    out.last_sync = SyncRunOut.model_validate(last_sync) if last_sync else None
    return out


@router.get("", response_model=list[RegionOut])
def list_regions(db: Session = Depends(get_db)):
    regions = db.query(Region).order_by(Region.created_at.asc()).all()
    syncs = _latest_syncs(db, [r.id for r in regions])
    result = []
    for r in regions:
        out = RegionOut.model_validate(r)
        out.stats = RegionStatsOut(**region_stats_light(db, r.id))
        last_sync = syncs.get(r.id)
        out.last_sync = SyncRunOut.model_validate(last_sync) if last_sync else None
        result.append(out)
    return result


@router.post("", response_model=RegionOut, status_code=201)
def create_region(data: RegionCreate, db: Session = Depends(get_db)):
    try:
        region = region_service.create_region(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _region_out(db, region)


@router.get("/{region_id}", response_model=RegionOut)
def get_region(region_id: int, db: Session = Depends(get_db)):
    return _region_out(db, _get_region(db, region_id))


@router.patch("/{region_id}", response_model=RegionOut)
def update_region(region_id: int, data: RegionUpdate, db: Session = Depends(get_db)):
    region = _get_region(db, region_id)
    try:
        region = region_service.update_region(db, region, data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _region_out(db, region)


@router.delete("/{region_id}", status_code=204)
def delete_region(region_id: int, db: Session = Depends(get_db)):
    region_service.delete_region(db, _get_region(db, region_id))


@router.post("/{region_id}/sync", response_model=SyncRunOut)
def sync_region_now(region_id: int, db: Session = Depends(get_db)):
    region = _get_region(db, region_id)
    sync_service.sync_region(db, region)
    run = (
        db.query(SyncRun)
        .filter(SyncRun.region_id == region.id)
        .order_by(SyncRun.started_at.desc())
        .first()
    )
    return SyncRunOut.model_validate(run)


@router.post("/{region_id}/export")
def export_region(region_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import StreamingResponse

    _get_region(db, region_id)
    from ..services.export_service import export_region_xlsx

    data = export_region_xlsx(db, region_id)
    filename = f"region_{region_id}.xlsx"
    return StreamingResponse(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
