"""轻量数据库迁移器。

SQLite 场景：启动时比对 `PRAGMA table_info`，对缺失列执行
`ALTER TABLE ADD COLUMN`（幂等、无损），并在 meta 表记录 schema 版本。
新库由 SQLAlchemy `create_all` 建全量表，本迁移器负责旧库升级。
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "6"

# 每个表需要确保存在的列（仅 ADD COLUMN 场景，全部可空）
_COLUMN_DEFS: dict[str, list[str]] = {
    "properties": [
        "data_source VARCHAR(32) DEFAULT 'unknown'",
        "image_url VARCHAR(512)",
        "image_count INTEGER",
        "reduced_flag BOOLEAN",
        "added_hint VARCHAR(32)",
        "new_home_flag BOOLEAN",
        "removed_at DATETIME",
        "relisted_at DATETIME",
        "miss_count INTEGER DEFAULT 0",
    ],
    "region_snapshots": [
        "median_price FLOAT",
    ],
    "sync_runs": [
        "data_source VARCHAR(32) DEFAULT 'unknown'",
        "complete BOOLEAN",
        "price_changed_count INTEGER DEFAULT 0",
        "status_changed_count INTEGER DEFAULT 0",
    ],
}


def _existing_columns(conn: Connection, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def _tables(conn: Connection) -> set[str]:
    rows = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'")
    ).fetchall()
    return {r[0] for r in rows}


def run_migrations(conn: Connection) -> None:
    existing = _tables(conn)
    for table, columns in _COLUMN_DEFS.items():
        if table not in existing:
            continue
        current = _existing_columns(conn, table)
        for col_def in columns:
            col_name = col_def.split(" ", 1)[0]
            if col_name not in current:
                conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {col_def}")
                )
                logger.info("迁移: %s 添加列 %s", table, col_name)

    # 旧库没有记录数据源时，从 URL 尽可能恢复；无法判断的保留 unknown。
    if "properties" in existing and "data_source" in _existing_columns(conn, "properties"):
        conn.execute(
            text(
                "UPDATE properties SET data_source = CASE "
                "WHEN url LIKE '%onthemarket.com%' THEN 'onthemarket' "
                "WHEN url LIKE '%rightmove.co.uk%' THEN 'rightmove' "
                "WHEN data_source IS NULL OR data_source = '' THEN 'unknown' "
                "ELSE data_source END"
            )
        )

    conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS meta (key VARCHAR(64) PRIMARY KEY, value VARCHAR(255) NOT NULL)"
        )
    )
    conn.execute(
        text(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', :v)"
        ),
        {"v": SCHEMA_VERSION},
    )
    conn.commit()
