"""邮编地理编码：与数据源解耦，mock 模式完全离线。

真实地理编码走 postcodes.io（独立于 scraper 数据源，避免区域管理
依赖 Rightmove 适配器导致离线演示仍在联网）。
"""

from __future__ import annotations

import logging
import urllib.parse

import requests

from ..core.config import settings

logger = logging.getLogger(__name__)

_POSTCODES_IO_URL = "https://api.postcodes.io/postcodes/{}"


def geocode_postcode(postcode: str) -> tuple[float, float] | None:
    """邮编 → (lat, lng)。mock 模式返回确定性离线坐标，绝不联网。"""
    if settings.data_source == "mock":
        from ..scraper.mock import MockDataSource

        return MockDataSource().geocode(postcode)
    return _geocode_remote(postcode)


def _geocode_remote(postcode: str) -> tuple[float, float] | None:
    try:
        resp = requests.get(
            _POSTCODES_IO_URL.format(urllib.parse.quote(postcode)),
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json().get("result")
        if result:
            return result["latitude"], result["longitude"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("geocode %s failed: %s", postcode, exc)
    return None
