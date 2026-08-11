"""SQLite access layer.

The whole database is a handful of tables, so there is no ORM here. The rules
that matter:

1. Every query is parameterized. String formatting a value into SQL is a bug.
2. Writes that must be atomic go through :func:`transaction`, which holds a
   write lock for the duration of the block.
3. Money is stored as integer cents. Never as a float.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.config import get_settings

_local = threading.local()
_write_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    sku          TEXT PRIMARY KEY,
    name         TEXT    NOT NULL,
    price_cents  INTEGER NOT NULL CHECK (price_cents >= 0),
    stock        INTEGER NOT NULL CHECK (stock >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    id           TEXT PRIMARY KEY,
    customer_id  TEXT    NOT NULL,
    status       TEXT    NOT NULL,
    subtotal_cents INTEGER NOT NULL,
    discount_cents INTEGER NOT NULL DEFAULT 0,
    tax_cents      INTEGER NOT NULL,
    total_cents    INTEGER NOT NULL,
    promo_code     TEXT,
    created_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders (customer_id, created_at DESC);

CREATE TABLE IF NOT EXISTS order_items (
    order_id         TEXT    NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    sku              TEXT    NOT NULL,
    quantity         INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents INTEGER NOT NULL,
    PRIMARY KEY (order_id, sku)
);

CREATE TABLE IF NOT EXISTS promo_codes (
    code            TEXT PRIMARY KEY,
    percent_off     REAL    NOT NULL,
    max_redemptions INTEGER NOT NULL,
    redemptions     INTEGER NOT NULL DEFAULT 0,
    active          INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS payments (
    id            TEXT PRIMARY KEY,
    order_id      TEXT    NOT NULL REFERENCES orders (id),
    status        TEXT    NOT NULL,
    amount_cents  INTEGER NOT NULL,
    gateway_ref   TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_gateway_ref
    ON payments (gateway_ref) WHERE gateway_ref IS NOT NULL;
"""


def get_connection() -> sqlite3.Connection:
    """Return this thread's connection, opening it on first use."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(get_settings().database_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        _local.conn = conn
    return conn


def init_db() -> None:
    """Create tables if they are not there yet."""
    get_connection().executescript(SCHEMA)


def close_connection() -> None:
    """Close this thread's connection, if it has one."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Run a block as one atomic write.

    Read-modify-write sequences (stock decrements, redemption counters) must be
    inside this block or two concurrent requests can interleave and oversell.
    """
    conn = get_connection()
    with _write_lock:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except Exception:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")


def query(sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    """Run a parameterized SELECT and return every row."""
    return get_connection().execute(sql, params).fetchall()


def query_one(sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    """Run a parameterized SELECT and return the first row, if any."""
    return get_connection().execute(sql, params).fetchone()
