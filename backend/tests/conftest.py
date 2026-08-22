import os

os.environ.setdefault("UKH_DATA_SOURCE", "mock")
os.environ.setdefault("UKH_DATABASE_URL", "sqlite:///./test_ukhouse.db")

import pytest

from app import models
from app.core.database import SessionLocal, engine, init_db


@pytest.fixture(scope="session", autouse=True)
def _db_env():
    init_db()
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def db(_db_env):
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def clean_db(db):
    for table in reversed(models.Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
