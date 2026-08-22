"""OnTheMarket 数据源适配器。

实测：当前网络下无反爬拦截，普通 requests 即可获取真实挂牌数据。
- 邮编搜索：GET /async/text-search/?query={邮编}&search-type=for-sale → location slug
- 列表页：https://www.onthemarket.com/for-sale/property/{slug}/?radius={英里}&page={n}
- 详情页：https://www.onthemarket.com/details/{id}/ 的 __NEXT_DATA__（描述/卫浴/完整地址）

注意：OTM 不暴露房源坐标与完整邮编（隐私），地图只能显示区域圈。
"""

from __future__ import annotations

import json
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from ..core.config import settings
from .area import extract_area_from_features, extract_area_from_text
from .base import BaseDataSource, Listing, nearest_radius_miles

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.onthemarket.com/for-sale/property/"
TEXT_SEARCH_URL = "https://www.onthemarket.com/async/text-search/"
DETAIL_URL = "https://www.onthemarket.com/details/{}"

HEADERS = {
    "User-Agent": settings.user_agent,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

_CARD_SELECTOR = '[data-component="search-result-property-card"]'


class OnTheMarketDataSource(BaseDataSource):
    name = "onthemarket"

    # OTM 不暴露门牌号/完整邮编，物理指纹不可靠 → 关闭自动重挂合并，避免误并
    relist_merge = False

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.last_complete = True

    # ---------- 位置解析 ----------
    def resolve_location(self, postcode: str) -> tuple[str, str] | None:
        """邮编 → (location-slug, display_name)，如 ('se16-2ug', 'SE16 2UG')。"""
        resp = self._request(
            TEXT_SEARCH_URL,
            params={"query": postcode, "search-type": "for-sale"},
            accept="application/json",
        )
        if resp is None:
            return None
        try:
            completions = resp.json().get("completions") or []
        except ValueError:
            return None
        for c in completions:
            if c.get("location-type") == "postcode":
                return c.get("location-id"), c.get("name")
        if completions:
            c = completions[0]
            return c.get("location-id"), c.get("name")
        return None

    def geocode(self, postcode: str) -> tuple[float, float] | None:
        try:
            resp = self.session.get(
                f"https://api.postcodes.io/postcodes/{postcode.replace(' ', '')}",
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
        loc = self.resolve_location(postcode)
        if loc is None:
            logger.warning("无法解析邮编 %s 的 OnTheMarket 位置", postcode)
            self.last_complete = False
            return []
        slug = loc[0]
        radius_miles = nearest_radius_miles(radius_km)
        listings: list[Listing] = []
        seen: set[str] = set()
        page_size: int | None = None
        self.last_complete = True
        for page in range(1, settings.othem_max_pages + 1):
            params: dict = {"radius": radius_miles}
            if page > 1:
                params["page"] = page
            html = self._fetch_page(f"{SEARCH_URL}{slug}/", params)
            if html is None:
                # 翻页失败：结果不完整，调用方不应据此判定消失
                self.last_complete = False
                logger.warning("OnTheMarket 第 %d 页抓取失败，结果不完整", page)
                break
            cards = _parse_cards(html)
            if not cards:
                if page == 1 and not _is_known_empty_search(html):
                    self.last_complete = False
                    logger.warning(
                        "OnTheMarket 第 1 页没有可解析房源，可能是反爬或页面结构变化，结果不完整"
                    )
                elif _is_blocked_page(html):
                    self.last_complete = False
                    logger.warning("OnTheMarket 返回疑似反爬页面，结果不完整")
                break
            fresh = [c for c in cards if c.listing_id not in seen]
            if not fresh:
                # 重复第一页通常意味着分页参数被忽略，不能据此判定列表已结束。
                self.last_complete = False
                logger.warning("OnTheMarket 第 %d 页与之前页面重复，结果不完整", page)
                break
            seen.update(c.listing_id for c in fresh)
            listings.extend(fresh)
            if page_size is None:
                page_size = len(cards)
            elif len(cards) < page_size:
                # 页面数量少于首屏，说明已经到达正常的最后一页。
                break
            time.sleep(settings.othem_delay_seconds)
        else:
            # 到达 max_pages 上限仍未抓完 → 不完整
            self.last_complete = False
        logger.info(
            "OnTheMarket 搜索 %s (半径 %.1fkm) -> %d 套房源 (完整=%s)",
            postcode, radius_km, len(listings), self.last_complete,
        )
        return listings

    def _fetch_page(self, url: str, params: dict) -> str | None:
        resp = self._request(url, params=params)
        if resp is None:
            return None
        return resp.text

    # ---------- 详情 ----------
    def fetch_detail(self, listing_id: str) -> dict:
        if not settings.othem_fetch_detail:
            return {}
        resp = self._request(DETAIL_URL.format(listing_id))
        if resp is None:
            return {}
        return _parse_detail(resp.text)

    # ---------- 通用请求 ----------
    def _request(self, url: str, params: dict | None = None, accept: str | None = None):
        headers = dict(HEADERS)
        if accept:
            headers["Accept"] = accept
        for attempt in range(3):
            try:
                resp = self.session.get(
                    url, params=params, headers=headers, timeout=settings.scraper_timeout
                )
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                logger.debug("请求失败 (%s) %s: %s", attempt + 1, url, exc)
                time.sleep(1.0 * (attempt + 1))
        return None

    def close(self) -> None:
        self.session.close()


def _parse_price(text: str) -> int | None:
    if not text:
        return None
    m = re.search(r"£?\s*([\d,]+)", text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_cards(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    listings: list[Listing] = []
    for card in soup.select(_CARD_SELECTOR):
        a = card.find("a", href=re.compile(r"/details/(\d+)"))
        if not a:
            continue
        m = re.search(r"/details/(\d+)", a["href"])
        pid = m.group(1)

        pt = card.select_one('[data-component="price-title"]')
        price = _parse_price(pt.get_text() if pt else "")

        ad = card.select_one("address")
        address = ad.get_text(strip=True) if ad else None

        title = card.get("title") or ""
        bedrooms = None
        ptype = None
        m2 = re.search(r"- (\d+) bedroom (.+?) for sale", title)
        if m2:
            bedrooms = int(m2.group(1))
            ptype = m2.group(2).strip()

        card_text = card.get_text(" ")
        card_text_l = card_text.lower()
        status = "listed"
        if "under offer" in card_text_l:
            status = "under_offer"
        elif "sold" in card_text_l:
            status = "sold"

        # 图片：取卡片内第一张缩略图 URL + 数量
        image_url = None
        image_count = 0
        imgs = card.find_all("img")
        image_count = len(imgs)
        for im in imgs:
            src = im.get("src") or ""
            if "media.onthemarket.com" in src and re.search(r"image-\d+-\d+x\d+\.jpg", src):
                image_url = src
                break

        # 即时信号：精确匹配 pill 文本，避免全文误判
        pill_texts = [
            (p.get_text(strip=True) or "").lower()
            for p in card.select('[data-component="pill"]')
        ]
        reduced_flag = any(t == "reduced" or t.startswith("reduced") for t in pill_texts)
        new_home_flag = any("new home" in t for t in pill_texts) or "new home" in title.lower()
        added_hint = None
        m3 = re.search(r"added\s*(>\s*)?(\d+)\s*days?", card_text, re.I)
        if m3:
            added_hint = f"added > {m3.group(2)} days"

        listings.append(
            Listing(
                listing_id=pid,
                url=f"https://www.onthemarket.com/details/{pid}/",
                price=price,
                bedrooms=bedrooms,
                property_type=ptype,
                address=address,
                status=status,
                # OTM 无门牌/街道/邮编 → 不伪造，避免指纹误判
                number=None,
                street=None,
                extra={
                    "image_url": image_url,
                    "image_count": image_count,
                    "reduced_flag": reduced_flag,
                    "new_home_flag": new_home_flag,
                    "added_hint": added_hint,
                    "floor_area_sqft": extract_area_from_text(card_text),
                },
            )
        )
    return listings


def _is_blocked_page(html: str) -> bool:
    text = BeautifulSoup(html, "html.parser").get_text(" ").lower()
    markers = (
        "captcha",
        "verify you are human",
        "access denied",
        "unusual traffic",
        "cf-chl-",
        "checking your browser",
    )
    return any(marker in text or marker in html.lower() for marker in markers)


def _is_known_empty_search(html: str) -> bool:
    """仅认可明确的无结果页面，未知空 HTML 一律按不完整处理。"""
    if _is_blocked_page(html):
        return False
    text = BeautifulSoup(html, "html.parser").get_text(" ").lower()
    return any(
        marker in text
        for marker in (
            "no properties found",
            "no results found",
            "we couldn't find any properties",
        )
    )


def _parse_detail(html: str) -> dict:
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.S,
    )
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
        prop = (data.get("props") or {}).get("initialReduxState", {}).get("property", {})
    except (ValueError, AttributeError):
        return {}
    result: dict = {}
    if prop.get("description"):
        result["description"] = prop["description"]
    if prop.get("bathrooms"):
        result["bathrooms"] = prop["bathrooms"]
    if prop.get("humanisedPropertyType"):
        result["property_type"] = prop["humanisedPropertyType"]
    # 面积：优先 features，其次描述
    area = extract_area_from_features(prop.get("features")) or extract_area_from_text(
        prop.get("description")
    )
    if area:
        result["floor_area_sqft"] = area
    return result
