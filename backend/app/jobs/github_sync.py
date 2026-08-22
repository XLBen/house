"""Run one sync in GitHub Actions without starting the web server."""

from __future__ import annotations

import json
import logging
import sys

from ..core.database import SessionLocal, init_db
from ..services.email_report import ensure_target_regions, send_email_report
from ..services.sync_service import sync_all


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    init_db()
    db = SessionLocal()
    try:
        ensure_target_regions(db)
        results = sync_all(db)
        send_email_report(db, results)
    finally:
        db.close()

    print(json.dumps({str(key): value for key, value in results.items()}, ensure_ascii=False))
    errors = [result for result in results.values() if result.get("error")]
    incomplete = [result for result in results.values() if not result.get("complete", True)]
    if incomplete:
        logging.warning("%d 个区域结果不完整，已跳过下架检测", len(incomplete))
    if errors:
        logging.error("%d 个区域同步失败", len(errors))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
