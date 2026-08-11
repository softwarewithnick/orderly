"""Shared fixtures.

Each test gets its own SQLite file and its own settings cache, so tests cannot
leak state into each other through the module-level connection or the
``lru_cache`` on :func:`app.config.get_settings`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import get_settings

API_KEY = "test-api-key"
WEBHOOK_SECRET = "test-webhook-secret"

SEED_PRODUCTS = [
    ("SKU-DESK", "Standing desk", 49900, 5),
    ("SKU-CHAIR", "Ergonomic chair", 29900, 2),
    ("SKU-LAMP", "Desk lamp", 4599, 100),
]


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch) -> Iterator[None]:
    monkeypatch.setenv("ORDERLY_DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("ORDERLY_API_KEY", API_KEY)
    monkeypatch.setenv("ORDERLY_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("ORDERLY_PAYMENT_API_KEY", "test-gateway-key")
    get_settings.cache_clear()
    db.close_connection()

    db.init_db()
    with db.transaction() as conn:
        conn.executemany(
            "INSERT INTO products (sku, name, price_cents, stock) VALUES (?, ?, ?, ?)",
            SEED_PRODUCTS,
        )

    yield

    db.close_connection()
    get_settings.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        test_client.headers["X-API-Key"] = API_KEY
        yield test_client
