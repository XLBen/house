from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class RegionProperty(Base):
    __tablename__ = "region_properties"
    __table_args__ = (UniqueConstraint("region_id", "property_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id"), index=True, nullable=False
    )
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id"), index=True, nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
