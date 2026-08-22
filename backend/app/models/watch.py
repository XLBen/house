from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PropertyWatch(Base):
    __tablename__ = "property_watch"
    __table_args__ = (UniqueConstraint("property_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
