"""每日变化 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..schemas.stats import ChangeSummary
from ..services.change_service import changes_for_region

router = APIRouter(tags=["changes"])


@router.get("/api/regions/{region_id}/changes", response_model=ChangeSummary)
def region_changes(
    region_id: int,
    date: str | None = Query(None, description="YYYY-MM-DD，默认今天"),
    since: str | None = Query(
        None, description="对比起点：last_sync 或 ISO 日期/时间（优先于 date）"
    ),
    db: Session = Depends(get_db),
):
    return changes_for_region(db, region_id, day=date, since=since)
