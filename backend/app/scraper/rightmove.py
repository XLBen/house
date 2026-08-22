"""Rightmove 数据源适配器。

说明：
- 位置解析用 los.rightmove.co.uk/typeahead（可用）。
- 房源搜索优先尝试旧 JSON 接口 api/_search（某些环境可用），
  失败则回退到 Playwright 加载搜索页并解析 DOM。
- 详情优先 property-detail API，回退 HTML 解析。
- 注意 Rightmove 有较强反爬（F5 系），可能需要：住宅 IP / 代理 / 有头模式。
  相关开关在 settings（UKH_RIGHTMOVE_USE_BROWSER / UKH_RIGHTMOVE_HEADLESS）。
"""

from __future__ import annotations

import logging
import re
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup

from ..core.config import settings
from .base import BaseDataSource, Listing

logger = logging.getLogger(__name__)

TYPEAHEAD_URL = "https://los.rightmove.co.uk/typeahead"
SEARCH_API_URL = "https://www.rightmove.co.uk/api/_search"
DETAIL_API_URL = "https://www.rightmove.co.uk/api/property-detail"
SEARCH_PAGE_URL = "https://www.rightmove.co.uk/property-for-sale/search.html"

_MILES = 1.609344

HEADERS = {
    "User-Agent": settings.user_agent,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.rightmove.co.uk/",
}

# 允许的半径档位（英里）；2km 落在 1 英里（1.6km）附近，取最近档位
_RADIUS_MILES_OPTIONS = [0.0, 0.25, 0.5, 1.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0]


def km_to_miles(km: float) -> float:
    return km / _MILES


def _nearest_radius_miles(km: float) -> float:
    miles = km_to_miles(km)
    return min(_RADIUS_MILES_OPTIONS, key=lambda r: abs(r - miles))


class RightmoveDataSource(BaseDataSource):
    name = "rightmove"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._browser = None

    # ---------- 位置解析 ----------
    def _typeahead(self, term: str) -> list[dict]:
        resp = self.session.get(
            TYPEAHEAD_URL,
            params={"query": term, "limit": 10, "exclude": "STREET"},
            timeout=settings.scraper_timeout,
        )
        resp.raise_for_status()
        return resp.json().get("matches") or []

    def resolve_location(self, postcode: str) -> tuple[str, str] | None:
        """返回 (location_identifier, display_name)，如 ("POSTCODE^837246", "SW1A 1AA")。"""
        matches = self._typeahead(postcode)
        for m in matches:
            if m.get("type") in ("POSTCODE", "OUTCODE", "REGION"):
                return f"{m['type']}^{m['id']}", m.get("displayName", postcode)
        if matches:
            m = matches[0]
            return f"{m['type']}^{m['id']}", m.get("displayName", postcode)
        return None

    def geocode(self, postcode: str) -> tuple[float, float] | None:
        try:
            resp = self.session.get(
                f"https://api.postcodes.io/postcodes/{urllib.parse.quote(postcode)}",
                timeout=10,
            )
            data = resp.json()
            result = data.get("result")
            if result:
                return result["latitude"], result["longitude"]
        except Exception as exc:  # noqa: BLE001
            logger.warning("geocode failed for %s: %s", postcode, exc)
        return None

    # ---------- 搜索 ----------
    def search(self, postcode: str, radius_km: float) -> list[Listing]:
        radius_miles = _nearest_radius_miles(radius_km)
        loc = self.resolve_location(postcode)
        listings: list[Listing] = []
        # 保守：仅在拿到完整 JSON 结果时才允许执行消失检测
        self.last_complete = False
        if loc:
            listings, json_ok = self._search_json(loc[0], radius_miles)
            if json_ok:
                self.last_complete = True
        if not listings and settings.rightmove_use_browser:
            listings, browser_complete = (
                self._search_browser(loc, radius_miles) if loc else ([], False)
            )
            self.last_complete = browser_complete
        if not listings:
            logger.warning(
                "Rightmove 搜索未返回任何房源 (postcode=%s, radius_km=%s)。"
                " 当前环境可能被反爬封锁，或该区域无在售房源。",
                postcode,
                radius_km,
            )
        return listings

    def _search_json(self, location_identifier: str, radius_miles: float) -> tuple[list[Listing], bool]:
        page_size = 24
        listings: list[Listing] = []
        seen: set[str] = set()
        try:
            total: int | None = None
            for page in range(settings.rightmove_max_pages):
                params = {
                    "locationIdentifier": location_identifier,
                    "radius": radius_miles,
                    "numberOfPropertiesPerPage": page_size,
                    "index": page * page_size,
                    "sortType": 6,
                    "viewType": "LIST",
                    "channel": "BUY",
                }
                resp = self.session.get(
                    SEARCH_API_URL, params=params, timeout=settings.scraper_timeout
                )
                if "json" not in resp.headers.get("content-type", ""):
                    logger.info("_search 接口返回非 JSON（可能被反爬拦截），改用浏览器模式。")
                    return [], False
                data = resp.json()
                properties = data.get("properties") or []
                if total is None:
                    raw_total = data.get("resultCount") or data.get("totalResults")
                    total = int(raw_total) if raw_total is not None else None
                for item in properties:
                    listing = self._parse_search_item(item)
                    if listing.listing_id not in seen:
                        seen.add(listing.listing_id)
                        listings.append(listing)
                if not properties:
                    return listings, True
                if total is not None and len(listings) >= total:
                    return listings, True
                if len(properties) < page_size:
                    return listings, total is None or len(listings) >= total
            logger.warning("Rightmove 搜索达到分页上限，结果不完整")
            return listings, False
        except Exception as exc:  # noqa: BLE001
            logger.warning("_search API 失败: %s", exc)
            return [], False

    def _search_browser(
        self, location: tuple[str, str], radius_miles: float
    ) -> tuple[list[Listing], bool]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("未安装 playwright，无法使用浏览器模式。")
            return [], False

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=settings.rightmove_headless,
                channel=settings.rightmove_channel or None,
            )
            context = browser.new_context(
                user_agent=settings.user_agent,
                locale="en-GB",
                viewport={"width": 1400, "height": 1000},
            )
            page = context.new_page()
            listings: list[Listing] = []
            seen: set[str] = set()
            complete = False
            for page_index in range(settings.rightmove_max_pages):
                url = (
                    f"{SEARCH_PAGE_URL}?searchLocation={urllib.parse.quote(location[1])}"
                    f"&useLocationIdentifier=true&locationIdentifier={urllib.parse.quote(location[0])}"
                    f"&radius={radius_miles}&index={page_index * 24}&sortType=6&channel=BUY"
                )
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(8000)
                page_listings = self._parse_search_html(page.content(), radius_miles)
                fresh = [p for p in page_listings if p.listing_id not in seen]
                if not fresh:
                    complete = page_index > 0 or bool(listings)
                    break
                listings.extend(fresh)
                seen.update(p.listing_id for p in fresh)
                if len(page_listings) < 24:
                    complete = True
                    break
            else:
                logger.warning("Rightmove 浏览器搜索达到分页上限，结果不完整")
            browser.close()
        return listings, complete

    @staticmethod
    def _parse_search_item(p: dict) -> Listing:
        address = p.get("address") or {}
        display = p.get("displayAddress") or ""
        price = (p.get("price") or {}).get("amount")
        loc = p.get("location") or {}
        pid = str(p.get("id"))
        return Listing(
            listing_id=pid,
            url=f"https://www.rightmove.co.uk/properties/{pid}",
            price=price,
            bedrooms=p.get("bedrooms"),
            bathrooms=p.get("bathrooms"),
            property_type=p.get("propertySubType"),
            address=display,
            postcode=address.get("postalCode"),
            street=address.get("streetName"),
            locality=address.get("locality"),
            town=address.get("town"),
            lat=loc.get("latitude"),
            lng=loc.get("longitude"),
        )

    @staticmethod
    def _parse_search_html(html: str, radius_miles: float) -> list[Listing]:
        """从搜索页 HTML 中提取房源卡片（浏览器模式回退）。"""
        soup = BeautifulSoup(html, "html.parser")
        listings: list[Listing] = []
        seen: set[str] = set()
        for card in soup.select('[data-testid^="property-card"], [class*="propertyCard"], [class*="l-searchResult"]'):
            link = card.select_one('a[href*="/properties/"]')
            if not link:
                continue
            m = re.search(r"/properties/(\d+)", link.get("href", ""))
            if not m:
                continue
            pid = m.group(1)
            if pid in seen:
                continue
            seen.add(pid)
            price_el = card.select_one('[class*="price"], [data-testid="property-price"]')
            price_text = price_el.get_text() if price_el else ""
            price = _parse_price(price_text)
            beds_el = card.select_one('[class*="bedrooms"], [data-testid="bedroom-number"]')
            bedrooms = int(re.search(r"\d+", beds_el.get_text()).group()) if beds_el else None
            addr_el = card.select_one('[class*="address"], [data-testid="property-address"]')
            address = addr_el.get_text(strip=True) if addr_el else None
            listings.append(
                Listing(
                    listing_id=pid,
                    url=f"https://www.rightmove.co.uk/properties/{pid}",
                    price=price,
                    bedrooms=bedrooms,
                    address=address,
                )
            )
        return listings

    # ---------- 详情 ----------
    def fetch_detail(self, listing_id: str) -> dict:
        """尽力获取详情字段，返回 dict（description / status 等）。失败返回 {}。"""
        try:
            resp = self.session.get(
                DETAIL_API_URL,
                params={"propertyId": listing_id},
                timeout=settings.scraper_timeout,
            )
            if "json" in resp.headers.get("content-type", ""):
                data = resp.json()
                return {
                    "description": data.get("propertyDescription"),
                    "status": _map_status(data.get("soldStatus")),
                }
        except Exception as exc:  # noqa: BLE001
            logger.debug("detail API failed for %s: %s", listing_id, exc)
        return {}

    def close(self) -> None:
        self.session.close()


def _parse_price(text: str) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _map_status(s: str | None) -> str:
    if not s:
        return "listed"
    v = s.lower()
    if "sold" in v:
        return "sold"
    if "offer" in v or "agreed" in v:
        return "under_offer"
    return "listed"
