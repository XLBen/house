from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Property(Base, TimestampMixin):
    __tablename__ = "properties"
    __table_args__ = (UniqueConstraint("data_source", "listing_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # 主身份：数据源挂牌 ID（如 Rightmove listing id）。
    # data_source 一并参与查询，避免切换数据源后误更新另一平台的房源。
    listing_id: Mapped[str] = mapped_column(String(64), index=True)
    data_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown", index=True
    )
    # 物理身份指纹：地址+卧室+类型（不含描述），用于下架重上架的合并
    fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)

    postcode: Mapped[str | None] = mapped_column(String(16), index=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    locality: Mapped[str | None] = mapped_column(String(120), nullable=True)
    town: Mapped[str | None] = mapped_column(String(120), nullable=True)

    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    property_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    floor_area_sqft: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 图片（引用数据源 CDN）
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 即时信号（数据源自带，当天可用）
    reduced_flag: Mapped[bool | None] = mapped_column(nullable=True)
    added_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 如 "> 14 days"
    new_home_flag: Mapped[bool | None] = mapped_column(nullable=True)

    # listed / under_offer / sold / removed
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="listed")
    current_price: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 从市场消失（检测到的）时间 / 重新挂牌时间
    removed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    relisted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 连续缺席同步次数（C1 防误判消失的宽限期计数）
    miss_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
