"""Stock reservation.

The only hard rule in this module: checking stock and decrementing it is one
atomic step. Two requests for the last unit must not both succeed, so the
decrement is written as a conditional UPDATE (``WHERE stock >= ?``) inside a
write transaction, and we trust the row count rather than a value we read
earlier.
"""

from __future__ import annotations

import sqlite3

from app.models import OrderItemIn
from app.services.pricing import PricedLine


class InventoryError(Exception):
    """Base class for stock problems."""


class UnknownSku(InventoryError):
    def __init__(self, sku: str) -> None:
        super().__init__(f"Unknown SKU: {sku}")
        self.sku = sku


class InsufficientStock(InventoryError):
    def __init__(self, sku: str, requested: int, available: int) -> None:
        super().__init__(f"Only {available} of {sku} left, {requested} requested")
        self.sku = sku
        self.requested = requested
        self.available = available


def reserve(conn: sqlite3.Connection, items: list[OrderItemIn]) -> list[PricedLine]:
    """Take ``items`` out of stock and return them priced at catalogue price.

    Must be called inside :func:`app.db.transaction`. Raises before any stock
    moves if a SKU is unknown; raises mid-way only if another writer beat us to
    the last unit, in which case the surrounding transaction rolls back.
    """
    lines: list[PricedLine] = []

    for item in items:
        row = conn.execute(
            "SELECT sku, price_cents, stock FROM products WHERE sku = ?",
            (item.sku,),
        ).fetchone()
        if row is None:
            raise UnknownSku(item.sku)

        # Conditional decrement: if another transaction already took the stock,
        # this matches zero rows and we fail instead of overselling.
        cursor = conn.execute(
            "UPDATE products SET stock = stock - ? WHERE sku = ? AND stock >= ?",
            (item.quantity, item.sku, item.quantity),
        )
        if cursor.rowcount == 0:
            raise InsufficientStock(item.sku, item.quantity, row["stock"])

        lines.append(
            PricedLine(
                sku=row["sku"],
                quantity=item.quantity,
                unit_price_cents=row["price_cents"],
            )
        )

    return lines


def release(
    conn: sqlite3.Connection,
    lines: list[PricedLine],
    *,
    reason: str = "payment_failed",
) -> None:
    """Put reserved stock back, e.g. after a payment is declined.

    Every release is also written to ``stock_events``, so that a later audit can
    tell an automatic restock apart from a manual inventory correction. Without
    that trail, a discrepancy at the end of the month is unattributable.
    """
    for line in lines:
        conn.execute(
            "UPDATE products SET stock = stock + ? WHERE sku = ?",
            (line.quantity, line.sku),
        )
        conn.execute(
            "INSERT INTO stock_events (sku, delta, reason) VALUES (?, ?, ?)",
            (line.sku, line.quantity, reason),
        )
