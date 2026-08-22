"""APScheduler：每天 0 点自动全量同步。"""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from .core.config import settings
from .core.database import SessionLocal
from .models import Region
from .services.dates import local_date, local_today
from .services.email_report import ensure_target_regions, send_email_report
from .services.sync_service import sync_all

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _job_sync_all() -> None:
    logger.info("定时同步开始 (每天 %s)", _sync_times_text())
    db = SessionLocal()
    try:
        ensure_target_regions(db)
        results = sync_all(db)
        errors = [result for result in results.values() if result.get("error")]
        incomplete = [result for result in results.values() if not result.get("complete", True)]
        if errors:
            logger.error("定时同步有 %d 个区域失败", len(errors))
        if incomplete:
            logger.warning("定时同步有 %d 个区域结果不完整，已跳过消失检测", len(incomplete))
        send_email_report(db, results)
    except Exception as exc:  # noqa: BLE001
        logger.exception("定时同步失败: %s", exc)
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)
    for index, (hour, minute) in enumerate(_sync_times()):
        _scheduler.add_job(
            _job_sync_all,
            CronTrigger(hour=hour, minute=minute),
            id=f"daily_sync_{index}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=26 * 60 * 60,
        )
    _scheduler.start()
    if _needs_catch_up():
        _scheduler.add_job(
            _job_sync_all,
            DateTrigger(
                run_date=datetime.now(ZoneInfo(settings.scheduler_timezone))
            ),
            id="startup_catch_up",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=26 * 60 * 60,
        )
        logger.warning("检测到错过最近同步，已安排启动补同步")
    logger.info("调度器已启动：每天 %s (%s)", _sync_times_text(), settings.scheduler_timezone)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def _needs_catch_up() -> bool:
    """服务在错过午夜后启动时，安排一次补同步。"""
    db = SessionLocal()
    try:
        today = datetime.fromisoformat(local_today()).date()
        regions = db.query(Region).filter(Region.is_active.is_(True)).all()
        return any(
            region.last_synced_at is None
            or (local_date(region.last_synced_at) or today) < today
            for region in regions
        )
    finally:
        db.close()


def _sync_times() -> list[tuple[int, int]]:
    values: list[tuple[int, int]] = []
    for raw in settings.sync_times.split(","):
        try:
            hour_text, minute_text = raw.strip().split(":", 1)
            hour, minute = int(hour_text), int(minute_text)
        except ValueError as exc:
            raise ValueError(f"UKH_SYNC_TIMES 格式错误: {raw!r}") from exc
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"UKH_SYNC_TIMES 时间超出范围: {raw!r}")
        if (hour, minute) not in values:
            values.append((hour, minute))
    return values


def _sync_times_text() -> str:
    return ", ".join(f"{hour:02d}:{minute:02d}" for hour, minute in _sync_times())
