from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

# 事件类型：new / price_change / status_change / delisted
EVENT_NEW = "new"
EVENT_PRICE_CHANGE = "price_change"
EVENT_STATUS_CHANGE = "status_change"
EVENT_DELISTED = "delisted"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id"), index=True, nullable=False
    )
    region_id: Mapped[int | None] = mapped_column(
        ForeignKey("regions.id"), index=True, nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    old_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
