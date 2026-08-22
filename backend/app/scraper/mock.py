"""模拟数据源：用于测试 / 演示 / 离线运行。

设计目标：
- 确定性：同一 (postcode, radius) 生成同一批房源，跨天稳定；
- 可测变化：价格按日期做小幅漂移，让"每日变化检测"可演示；
- 身份稳定：listing_id 与指纹跨天不变，只有价格/状态变化。
"""

from __future__ import annotations

import hashlib
import random
from datetime import date

from .base import BaseDataSource, Listing

_STREETS = [
    "Church Street", "Queen's Road", "Victoria Avenue", "Mill Lane",
    "King Street", "Grove Park Road", "Beacon Hill", "Riverside Drive",
]
_TYPES = ["Detached", "Semi-Detached", "Terraced", "Flat", "Bungalow", "Maisonette"]
_FIRST = [
    "Harry", "Grace", "Oliver", "Freya", "Noah", "Emily", "Oscar", "Lily",
    "George", "Maya", "Freddie", "Amelia",
]


def _seed(postcode: str, radius_km: float) -> int:
    return int(hashlib.md5(f"{postcode}|{radius_km}".encode()).hexdigest(), 16) % (2**32)


class MockDataSource(BaseDataSource):
    name = "mock"

    def __init__(self, today: date | None = None) -> None:
        self.today = today or date.today()
        self.last_complete = True

    def geocode(self, postcode: str) -> tuple[float, float] | None:
        rng = random.Random(_seed(postcode, 0))
        # 以 (51.5, -0.12) 附近为基准，生成确定性的"该邮编中心点"
        lat = 51.0 + rng.random() * 3.0
        lng = -2.5 + rng.random() * 4.0
        return round(lat, 6), round(lng, 6)

    def search(self, postcode: str, radius_km: float) -> list[Listing]:
        rng = random.Random(_seed(postcode, radius_km))
        center_lat, center_lng = self.geocode(postcode)
        count = rng.randint(30, 45)
        listings: list[Listing] = []
        used: set[int] = set()
        for i in range(count):
            idx = i
            while idx in used:
                idx = rng.randint(100000, 999999)
            used.add(idx)
            base_price = rng.randint(220_000, 950_000)
            # 价格按天数做确定性漂移：约 1/4 房源每天小降/小涨，模拟市场变化
            day_no = self.today.toordinal()
            drift_seed = idx * 7 + day_no
            drift = random.Random(drift_seed).choice([0, 0, 0, -15000, -25000, 12000])
            price = max(50_000, base_price + drift)
            street = rng.choice(_STREETS)
            house_no = rng.randint(1, 120)
            beds = rng.choice([1, 2, 2, 3, 3, 4, 5])
            ptype = rng.choice(_TYPES)
            outcode = postcode.split(" ")[0] if postcode else "LS1"
            address = f"{house_no} {street}, {outcode} {rng.randint(1, 9)}{rng.choice('ABCDEFGHIJ')}{rng.randint(1, 9)}{rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}"
            lat = center_lat + rng.uniform(-0.01, 0.01)
            lng = center_lng + rng.uniform(-0.015, 0.015)
            listings.append(
                Listing(
                    listing_id=str(idx),
                    url=f"https://www.rightmove.co.uk/properties/{idx}",
                    price=price,
                    bedrooms=beds,
                    bathrooms=rng.choice([1, 1, 2, 2, 3]),
                    property_type=ptype,
                    address=address,
                    postcode=postcode,
                    street=street,
                    town=outcode,
                    number=str(house_no),
                    lat=round(lat, 6),
                    lng=round(lng, 6),
                    description=(
                        f"{ptype} in {outcode}. {beds} bedrooms. "
                        f"A lovely {rng.choice(['refurbished', 'modern', 'character', 'spacious'])} home "
                        f"with {rng.choice(['garden', 'garage', 'parking', 'balcony'])}. "
                        f"EPC rating {rng.choice(['C', 'D', 'E', 'B'])}."
                    ),
                )
            )
        # 确定性排序，便于对比
        listings.sort(key=lambda l: l.listing_id)
        return listings
