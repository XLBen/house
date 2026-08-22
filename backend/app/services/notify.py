"""同步完成通知：通用 webhook 或 Telegram。

配置（backend/.env）：
  UKH_NOTIFY_WEBHOOK_URL=...        通用 webhook（POST JSON）
  UKH_NOTIFY_TELEGRAM_TOKEN=...     Telegram bot token
  UKH_NOTIFY_TELEGRAM_CHAT_ID=...   Telegram chat id
未配置则静默跳过（不影响同步）。
"""

from __future__ import annotations

import logging

import requests

from ..core.config import settings
from ..models import Event, Property

logger = logging.getLogger(__name__)


def _changes_snapshot(db, region_id: int, limit: int = 5) -> dict:
    """取该区域最近一次同步产生的变化，用于通知摘要。"""
    from ..models import SyncRun

    latest = (
        db.query(SyncRun)
        .filter(SyncRun.region_id == region_id, SyncRun.status == "success")
        .order_by(SyncRun.started_at.desc())
        .first()
    )
    if latest is None:
        return {"new": [], "delisted": [], "price_changes": []}
    boundary = latest.started_at
    events = (
        db.query(Event)
        .filter(Event.region_id == region_id, Event.occurred_at >= boundary)
        .order_by(Event.occurred_at.desc())
        .all()
    )
    result = {"new": [], "delisted": [], "price_changes": []}
    for ev in events:
        prop = db.get(Property, ev.property_id)
        item = {
            "address": prop.address if prop else ev.property_id,
            "price": prop.current_price if prop else None,
            "url": prop.url if prop else None,
        }
        if ev.event_type == "new":
            result["new"].append(item)
        elif ev.event_type == "delisted":
            result["delisted"].append(item)
        elif ev.event_type == "price_change":
            result["price_changes"].append(item)
        if len(result["new"]) + len(result["delisted"]) + len(result["price_changes"]) >= limit * 3:
            break
    result["new"] = result["new"][:limit]
    result["delisted"] = result["delisted"][:limit]
    result["price_changes"] = result["price_changes"][:limit]
    return result


def build_message(region_name: str, result: dict, changes: dict) -> str:
    price_changed = result.get("price_changed_count", result.get("changed_count", 0))
    status_changed = result.get("status_changed_count", 0)
    lines = [f"[UK House Invest] {region_name} 同步完成"]
    lines.append(
        f"本次：新增 {result['new_count']} · 消失 {result['delisted_count']} · "
        f"调价 {price_changed}" + (f" · 状态变化 {status_changed}" if status_changed else "")
    )
    if result.get("error"):
        lines.append(f"⚠️ 异常：{result['error'][:200]}")
    if changes["new"]:
        lines.append("")
        lines.append("🆕 新增：")
        for it in changes["new"][:5]:
            p = f"£{it['price']:,}" if it["price"] else "—"
            lines.append(f"  · {p} {it['address']} {it['url'] or ''}")
    if changes["delisted"]:
        lines.append("")
        lines.append("➖ 消失（可能售出/下架）：")
        for it in changes["delisted"][:5]:
            lines.append(f"  · {it['address']}")
    if changes["price_changes"]:
        lines.append("")
        lines.append("💰 调价：")
        for it in changes["price_changes"][:5]:
            lines.append(f"  · {it['address']}")
    return "\n".join(lines)


def send_message(text: str) -> None:
    if not text.strip():
        return
    if settings.notify_webhook_url:
        try:
            requests.post(
                settings.notify_webhook_url,
                json={"text": text},
                timeout=10,
            )
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("webhook 通知失败: %s", exc)
    if settings.notify_telegram_token and settings.notify_telegram_chat_id:
        try:
            requests.post(
                f"https://api.telegram.org/bot{settings.notify_telegram_token}/sendMessage",
                data={
                    "chat_id": settings.notify_telegram_chat_id,
                    "text": text,
                },
                timeout=10,
            )
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram 通知失败: %s", exc)


def notify_region_sync(db, region, result: dict) -> None:
    if not settings.notify_webhook_url and not (
        settings.notify_telegram_token and settings.notify_telegram_chat_id
    ):
        return
    try:
        changes = _changes_snapshot(db, region.id)
        msg = build_message(region.name, result, changes)
        send_message(msg)
    except Exception as exc:  # noqa: BLE001
        logger.warning("构造同步通知失败: %s", exc)
