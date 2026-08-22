import sqlite3

from sqlalchemy import create_engine, text

from app.core.migrations import run_migrations


def _make_old_db(path: str) -> None:
    """构造一个 v1 老库（无新列），含一行数据。"""
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE properties (
            id INTEGER PRIMARY KEY,
            listing_id TEXT UNIQUE,
            fingerprint TEXT,
            postcode TEXT,
            lat REAL, lng REAL,
            address TEXT, number TEXT, street TEXT, locality TEXT, town TEXT,
            bedrooms INTEGER, bathrooms INTEGER, property_type TEXT, floor_area_sqft REAL,
            description TEXT, url TEXT,
            status TEXT, current_price INTEGER,
            first_seen_at DATETIME, last_seen_at DATETIME,
            created_at DATETIME, updated_at DATETIME
        )
        """
    )
    conn.execute(
        "INSERT INTO properties (listing_id, status, first_seen_at, last_seen_at) "
        "VALUES ('1001', 'listed', '2026-01-01', '2026-01-01')"
    )
    conn.commit()
    conn.close()


def test_migration_adds_columns_keeps_data(tmp_path):
    db = tmp_path / "old.db"
    _make_old_db(str(db))
    engine = create_engine(f"sqlite:///{db}")
    with engine.connect() as conn:
        run_migrations(conn)
        cols = {
            r[1] for r in conn.execute(text("PRAGMA table_info(properties)")).fetchall()
        }
        for new_col in [
            "image_url", "image_count", "reduced_flag", "added_hint",
            "new_home_flag", "removed_at", "relisted_at", "miss_count",
        ]:
            assert new_col in cols, f"缺少列 {new_col}"
        # 老数据保留
        row = conn.execute(
            text("SELECT listing_id, status FROM properties")
        ).fetchone()
        assert row == ("1001", "listed")
        # schema 版本已记录
        ver = conn.execute(
            text("SELECT value FROM meta WHERE key='schema_version'")
        ).fetchone()
        assert ver is not None and ver[0] == "6"
    engine.dispose()


def test_migration_idempotent(tmp_path):
    db = tmp_path / "old.db"
    _make_old_db(str(db))
    engine = create_engine(f"sqlite:///{db}")
    with engine.connect() as conn:
        run_migrations(conn)
        run_migrations(conn)  # 再跑一次不应报错
        cols = {
            r[1] for r in conn.execute(text("PRAGMA table_info(properties)")).fetchall()
        }
        assert "removed_at" in cols
    engine.dispose()
