"""Excel 导出服务。"""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from sqlalchemy.orm import Session

from ..models import Property, RegionProperty


def export_region_xlsx(db: Session, region_id: int) -> BytesIO:
    props = (
        db.query(Property)
        .join(RegionProperty, RegionProperty.property_id == Property.id)
        .filter(RegionProperty.region_id == region_id)
        .order_by(Property.current_price.desc())
        .all()
    )
    wb = Workbook()
    ws = wb.active
    ws.title = "Properties"
    ws.append(
        [
            "listing_id", "address", "postcode", "town", "bedrooms",
            "bathrooms", "property_type", "current_price", "status",
            "first_seen_at", "last_seen_at", "url", "description",
        ]
    )
    for p in props:
        ws.append(
            [
                p.listing_id, p.address, p.postcode, p.town, p.bedrooms,
                p.bathrooms, p.property_type, p.current_price, p.status,
                p.first_seen_at.isoformat() if p.first_seen_at else None,
                p.last_seen_at.isoformat() if p.last_seen_at else None,
                p.url, p.description,
            ]
        )
    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out
