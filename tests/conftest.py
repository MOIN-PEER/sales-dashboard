"""Tests run against a fresh database in a temporary folder, never the real data/sales.db."""

import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_TMP_DB = Path(os.environ.setdefault("SALES_DB_PATH", str(ROOT / ".pytest_cache" / "test_sales.db")))
_TMP_DB.parent.mkdir(parents=True, exist_ok=True)
if _TMP_DB.exists():
    _TMP_DB.unlink()

from sales_dashboard.generate_data import build_database  # noqa: E402

build_database(_TMP_DB)


@pytest.fixture(scope="session")
def con():
    from sales_dashboard import queries
    c = queries.connect(_TMP_DB)
    yield c
    c.close()


@pytest.fixture(scope="session")
def raw():
    c = sqlite3.connect(_TMP_DB)
    yield c
    c.close()


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from sales_dashboard.api import app
    return TestClient(app)
