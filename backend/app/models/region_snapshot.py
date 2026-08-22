from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class RegionSnapshot(Base):
    __tablename__ = "region_snapshots"
    __table_args__ = (UniqueConstraint("region_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id"), index=True, nullable=False
    )
    date: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    active_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    price_change_count: Mapped[int] = mapped_column(Integer, default=0)
    delisted_count: Mapped[int] = mapped_column(Integer, default=0)
