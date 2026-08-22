from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int | None] = mapped_column(
        ForeignKey("regions.id"), index=True, nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # running / success / error
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    data_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown"
    )
    # 本次搜索是否完整（翻页失败/超页数上限 → False，结果可能不全）
    complete: Mapped[bool | None] = mapped_column(nullable=True)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    # 总变化数 = 调价数 + 状态变化数（历史字段，保留兼容）
    changed_count: Mapped[int] = mapped_column(Integer, default=0)
    price_changed_count: Mapped[int] = mapped_column(Integer, default=0)
    status_changed_count: Mapped[int] = mapped_column(Integer, default=0)
    delisted_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
