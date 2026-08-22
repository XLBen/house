"""房源查询 API（薄层：参数校验 + 转发 service）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models import Property
from ..schemas.property import EventOut, PriceHistoryOut, PropertyDetail
from ..services import property_service

router = APIRouter(tags=["properties"])


@router.get("/api/regions/{region_id}/properties")
def list_region_properties(
    region_id: int,
    status: str | None = Query(None),
    min_price: int | None = Query(None),
    max_price: int | None = Query(None),
    bedrooms: int | None = Query(None),
    property_type: str | None = Query(None, description="逗号分隔多选，支持 house/flat 家族"),
    has_image: bool | None = Query(None),
    min_image_count: int | None = Query(None),
    new_in_days: int | None = Query(None, description="只看最近 N 天上架"),
    q: str | None = Query(None),
    sort: str = Query("price_desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return property_service.list_region_properties(
        db,
        region_id,
        status=status,
        min_price=min_price,
        max_price=max_price,
        bedrooms=bedrooms,
        property_type=property_type,
        has_image=has_image,
        min_image_count=min_image_count,
        new_in_days=new_in_days,
        q=q,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/api/properties/{property_id}", response_model=PropertyDetail)
def get_property(property_id: int, db: Session = Depends(get_db)):
    prop = db.get(Property, property_id)
    if prop is None:
        raise HTTPException(status_code=404, detail="房源不存在")
    return property_service.get_property_detail(db, prop)


@router.get("/api/properties/{property_id}/history", response_model=list[PriceHistoryOut])
def get_price_history(property_id: int, db: Session = Depends(get_db)):
    return property_service.get_price_history(db, property_id)


@router.get("/api/properties/{property_id}/events", response_model=list[EventOut])
def get_property_events(property_id: int, db: Session = Depends(get_db)):
    return property_service.get_property_events(db, property_id)
