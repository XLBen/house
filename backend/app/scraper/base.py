"""数据源契约：所有数据源适配器（Rightmove / 未来 Zoopla / 测试 mock）都实现该接口。

这是整个系统的"扩展点"——新增数据源只需实现 BaseDataSource，
业务层（同步服务、变化检测、前端）零改动。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# 允许的半径档位（英里）——Rightmove 与 OnTheMarket 都使用固定档位
_RADIUS_MILES_OPTIONS = [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 30.0]

_MILES = 1.609344


def km_to_miles(km: float) -> float:
    return km / _MILES


def nearest_radius_miles(km: float) -> float:
    miles = km_to_miles(km)
    return min(_RADIUS_MILES_OPTIONS, key=lambda r: abs(r - miles))


@dataclass
class Listing:
    listing_id: str
    url: str
    price: int | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    property_type: str | None = None
    address: str | None = None
    postcode: str | None = None
    street: str | None = None
    locality: str | None = None
    town: str | None = None
    number: str | None = None
    lat: float | None = None
    lng: float | None = None
    description: str | None = None
    status: str = "listed"
    extra: dict = field(default_factory=dict)


class BaseDataSource(ABC):
    name: str = "base"

    # 下架重挂时是否允许按指纹合并（OTM 无门牌/邮编，指纹弱 → 关闭）
    relist_merge: bool = True
    # 最近一次 search 是否完整抓到全部结果（影响是否执行消失检测）
    last_complete: bool = True

    @abstractmethod
    def search(self, postcode: str, radius_km: float) -> list[Listing]:
        """以邮编为中心、radius_km 半径内搜索在售房源。"""

    @abstractmethod
    def geocode(self, postcode: str) -> tuple[float, float] | None:
        """把邮编解析为 (lat, lng)，用于区域中心点。"""

    def close(self) -> None:
        pass


def get_data_source(name: str) -> BaseDataSource:
    from .mock import MockDataSource
    from .onthemarket import OnTheMarketDataSource
    from .rightmove import RightmoveDataSource

    if name == "mock":
        return MockDataSource()
    if name == "rightmove":
        return RightmoveDataSource()
    if name == "onthemarket":
        return OnTheMarketDataSource()
    raise ValueError(f"未知数据源: {name}")
