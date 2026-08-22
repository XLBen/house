from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from .config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    from app import models  # noqa: F401

    models.Base.metadata.create_all(bind=engine)
    # 旧库升级：补列
    from .migrations import run_migrations

    with engine.connect() as conn:
        run_migrations(conn)
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        result = conn.execute(
            text(
                "UPDATE sync_runs SET status = 'error', complete = 0, "
                "finished_at = :finished_at, "
                "error = COALESCE(error, '同步进程中断，未正常完成') "
                "WHERE status = 'running' AND started_at < :cutoff"
            ),
            {"finished_at": datetime.now(timezone.utc).replace(tzinfo=None), "cutoff": cutoff},
        )
        if result.rowcount:
            logging.getLogger(__name__).warning(
                "已将 %d 条中断的同步记录标记为 error", result.rowcount
            )
        conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
