"""时间工具：全仓唯一的时间相关 helpers。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from ..core.config import settings


def now_utc() -> datetime:
    # 数据库目前保存 naive UTC，统一在边界处去掉 tzinfo。
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_today() -> str:
    return local_today()


def local_today() -> str:
    """返回调度时区的本地日期，而不是机器/UTC 日期。"""
    now = datetime.now(timezone.utc).astimezone(ZoneInfo(settings.scheduler_timezone))
    return now.date().isoformat()


def local_date(value: datetime | None) -> date | None:
    """把数据库中的 naive UTC 时间转换成调度时区日期。"""
    if value is None:
        return None
    aware = value.replace(tzinfo=timezone.utc)
    return aware.astimezone(ZoneInfo(settings.scheduler_timezone)).date()


def day_bounds(day: str) -> tuple[datetime, datetime]:
    """返回某个调度时区自然日对应的 naive UTC 范围。"""
    local_start = datetime.combine(date.fromisoformat(day), time.min).replace(
        tzinfo=ZoneInfo(settings.scheduler_timezone)
    )
    local_end = local_start + timedelta(days=1)
    start = local_start.astimezone(timezone.utc).replace(tzinfo=None)
    end = local_end.astimezone(timezone.utc).replace(tzinfo=None)
    return start, end
