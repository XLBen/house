"""Build and send the filtered property K-line report."""

from __future__ import annotations

import html
import json
import logging
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from sqlalchemy.orm import Session

from ..core.config import ROOT, settings
from ..identity.fingerprint import normalize_postcode
from ..models import PriceHistory, Property, Region, RegionProperty
from .dates import local_date
from .geocoder import geocode_postcode

logger = logging.getLogger(__name__)
TARGETS_FILE = ROOT / ".automation" / "targets.json"


def _targets() -> dict:
    try:
        return json.loads(TARGETS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("无法读取邮件筛选配置 %s: %s", TARGETS_FILE, exc)
        return {"price_min": 200000, "price_max": 300000, "max_properties": 8, "postcodes": []}


def ensure_target_regions(db: Session) -> None:
    """Ensure GitHub/local automation has a region for every target postcode."""
    changed = False
    for target in _targets().get("postcodes", []):
        postcode = normalize_postcode(target["postcode"])
        radius = float(target.get("radius_km", 2.0))
        exists = (
            db.query(Region)
            .filter(
                Region.center_postcode == postcode,
                Region.radius_km == radius,
                Region.is_active.is_(True),
            )
            .first()
        )
        if exists is not None:
            continue
        region = Region(
            name=target["name"],
            center_postcode=postcode,
            radius_km=radius,
            is_active=True,
        )
        point = geocode_postcode(postcode)
        if point:
            region.center_lat, region.center_lng = point
        db.add(region)
        changed = True
    if changed:
        db.commit()


def _daily_candles(history) -> list[dict]:
    grouped: dict[str, dict] = {}
    for item in sorted(history, key=lambda row: row.captured_at):
        day = local_date(item.captured_at)
        if day is None:
            continue
        key = day.isoformat()
        price = item.price
        candle = grouped.get(key)
        if candle is None:
            grouped[key] = {
                "date": key,
                "open": price,
                "close": price,
                "low": price,
                "high": price,
            }
        else:
            candle["close"] = price
            candle["low"] = min(candle["low"], price)
            candle["high"] = max(candle["high"], price)
    return list(grouped.values())


def _svg_chart(rows: list[dict]) -> str:
    width, card_width, card_height = 1160, 540, 270
    columns = 2
    rows_count = max(1, (len(rows) + columns - 1) // columns)
    height = 80 + rows_count * card_height
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfaf7"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#24323a}.axis{stroke:#d9dfdc}.up{stroke:#c94f55;fill:#c94f55}.down{stroke:#0b8f79;fill:#0b8f79}</style>',
        '<text x="32" y="38" font-size="22" font-weight="700">London ≤£300k Best-Value Property K-lines</text>',
    ]
    for index, row in enumerate(rows):
        x0 = 20 + (index % columns) * card_width
        y0 = 60 + (index // columns) * card_height
        candles = row["candles"]
        plot_x, plot_y, plot_w, plot_h = x0 + 20, y0 + 45, 490, 170
        values = [value for candle in candles for value in (candle["low"], candle["high"])]
        low, high = min(values), max(values)
        span = max(high - low, 1)

        def y(value: float) -> float:
            return plot_y + plot_h - ((value - low) / span) * plot_h

        label = html.escape(row["address"] or row["listing_id"])
        note = ""
        if row["vs_median"] < 0:
            note = f"低于区域均价 {abs(row['vs_median']):.0f}%"
        elif row["vs_median"] > 0:
            note = f"高于区域均价 {row['vs_median']:.0f}%"
        badge = "🔖" if row["reduced_flag"] else ("🆕" if row["new_home_flag"] else "")
        parts.append(f'<text x="{x0 + 20}" y="{y0 + 22}" font-size="15" font-weight="700">{badge}{label}</text>')
        parts.append(f'<text x="{x0 + 360}" y="{y0 + 22}" font-size="13">£{row["price"]:,} · {row["region"]}</text>')
        parts.append(f'<text x="{x0 + 360}" y="{y0 + 40}" font-size="12" fill="#0b8f79">{note}</text>')
        parts.append(f'<line class="axis" x1="{plot_x}" y1="{plot_y + plot_h}" x2="{plot_x + plot_w}" y2="{plot_y + plot_h}"/>')
        if not candles:
            parts.append(f'<text x="{plot_x}" y="{plot_y + 80}" font-size="13">暂无价格历史</text>')
            continue
        step = plot_w / max(len(candles), 1)
        body_width = min(18, max(5, step * 0.55))
        for candle_index, candle in enumerate(candles):
            x = plot_x + step * (candle_index + 0.5)
            color = "up" if candle["close"] >= candle["open"] else "down"
            parts.append(f'<line class="{color}" x1="{x:.1f}" y1="{y(candle["high"]):.1f}" x2="{x:.1f}" y2="{y(candle["low"]):.1f}" stroke-width="1.5"/>')
            top = min(y(candle["open"]), y(candle["close"]))
            body_height = max(2, abs(y(candle["open"]) - y(candle["close"])))
            parts.append(f'<rect class="{color}" x="{x - body_width / 2:.1f}" y="{top:.1f}" width="{body_width:.1f}" height="{body_height:.1f}"/>')
        parts.append(f'<text x="{plot_x}" y="{plot_y + plot_h + 22}" font-size="11">{candles[0]["date"]}</text>')
        parts.append(f'<text x="{plot_x + plot_w - 72}" y="{plot_y + plot_h + 22}" font-size="11">{candles[-1]["date"]}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _region_medians(db: Session, postcodes: list[str], config: dict) -> dict[str, float]:
    rows = (
        db.query(Region.center_postcode, Property.current_price)
        .join(RegionProperty, RegionProperty.region_id == Region.id)
        .join(Property, Property.id == RegionProperty.property_id)
        .filter(
            Region.center_postcode.in_(postcodes),
            Property.status.in_(("listed", "under_offer")),
            Property.current_price.isnot(None),
            Property.current_price <= int(config.get("price_max", 300000)),
        )
        .all()
    )
    buckets: dict[str, list[int]] = {}
    for postcode, price in rows:
        buckets.setdefault(postcode, []).append(price)
    medians: dict[str, float] = {}
    for postcode, prices in buckets.items():
        prices.sort()
        middle = len(prices) // 2
        if len(prices) % 2:
            medians[postcode] = float(prices[middle])
        elif prices:
            medians[postcode] = (prices[middle - 1] + prices[middle]) / 2.0
    return medians


def _value_score(price: int, median: float) -> tuple[float, float]:
    """性价比分：价格低于区域均价越多越优；带降价/新房标记再加分。"""
    if not median:
        return 1.0, 0.0
    ratio = price / median
    return ratio, (price - median) / median * 100


def build_report(db: Session) -> tuple[str, str]:
    config = _targets()
    price_max = int(config.get("price_max", 300000))
    postcodes = [normalize_postcode(item["postcode"]) for item in config.get("postcodes", [])]
    region_rows = db.query(Region).filter(
        Region.center_postcode.in_(postcodes), Region.is_active.is_(True)
    ).all()
    region_map = {region.id: region for region in region_rows}
    medians = _region_medians(db, postcodes, config)
    candidates = (
        db.query(Property, RegionProperty.region_id)
        .join(RegionProperty, RegionProperty.property_id == Property.id)
        .filter(
            RegionProperty.region_id.in_(region_map),
            Property.status.in_(("listed", "under_offer")),
            Property.current_price >= int(config.get("price_min", 200000)),
            Property.current_price <= price_max,
        )
        .all()
    )
    pooled: list[dict] = []
    seen_properties: set[int] = set()
    for prop, region_id in candidates:
        if prop.id in seen_properties:
            continue
        seen_properties.add(prop.id)
        region = region_map[region_id]
        median = medians.get(region.center_postcode, 0.0)
        ratio, vs_median = _value_score(prop.current_price or 0, median)
        if prop.reduced_flag:
            ratio *= 0.88
        if prop.new_home_flag:
            ratio *= 0.95
        history = db.query(PriceHistory).filter(
            PriceHistory.property_id == prop.id
        ).order_by(PriceHistory.captured_at.asc()).all()
        pooled.append({
            "listing_id": prop.listing_id,
            "address": prop.address,
            "price": prop.current_price,
            "region": region.name,
            "ratio": ratio,
            "vs_median": vs_median,
            "first_price": history[0].price if history else None,
            "reduced_flag": prop.reduced_flag,
            "new_home_flag": prop.new_home_flag,
            "first_seen_at": prop.first_seen_at,
            "candles": _daily_candles(history),
        })
    # 性价比分越低越优，同分取更早上架（新房）优先
    pooled.sort(key=lambda row: (row["ratio"], row["first_seen_at"]))
    rows = pooled[: int(config.get("max_properties", 8))]
    svg = _svg_chart(rows)
    subject = f"UK高性价比房源 K线 | ≤£{price_max:,} | {len(rows)}套"
    lines = []
    for row in rows:
        note = ""
        if row["vs_median"] < 0:
            note = f" 低于区域均价 {abs(row['vs_median']):.0f}%"
        elif row["vs_median"] > 0:
            note = f" 高于区域均价 {row['vs_median']:.0f}%"
        badge = "🔖降价" if row["reduced_flag"] else ("🆕新房" if row["new_home_flag"] else "")
        lines.append(f"{badge} {row['address'] or row['listing_id']} | £{row['price']:,}{note} | {row['region']}")
    plain = "只看 £300,000 以下、按性价比排序的房源 K 线见附件。\n\n" + "\n".join(lines)
    return subject, (plain, svg)


def send_email_report(db: Session, results: dict | None = None) -> None:
    if not all((settings.smtp_host, settings.smtp_username, settings.smtp_password)):
        return
    try:
        subject, (plain, svg) = build_report(db)
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.email_from or settings.smtp_username
        message["To"] = settings.email_to
        message.set_content(plain)
        message.add_attachment(
            svg.encode("utf-8"),
            maintype="image",
            subtype="svg+xml",
            filename="london-property-kline.svg",
        )
        context = ssl.create_default_context()
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context, timeout=30) as smtp:
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
                smtp.starttls(context=context)
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
        logger.info("邮件 K 线报告已发送到 %s", settings.email_to)
    except Exception as exc:  # noqa: BLE001
        logger.exception("邮件 K 线报告发送失败: %s", exc)
