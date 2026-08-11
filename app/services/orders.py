"""Order orchestration.

This module owns the order of operations for a checkout, which is the part that
is easy to get subtly wrong:

1. Reserve stock and write the order in one transaction, so a crash cannot leave
   stock decremented with no order to show for it.
2. Only then call the gateway, which is slow and outside our transaction.
3. If the charge fails, put the stock back and mark the order failed.

Steps 1 and 3 are transactional. Step 2 is not, and must never be run while a
write transaction is open -- holding SQLite's write lock across a network call
blocks every other checkout for as long as the gateway takes to answer.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import UTC, datetime

from app import db
from app.models import (
    OrderCreate,
    OrderItemOut,
    OrderOut,
    OrderPage,
    OrderStatus,
    Quote,
)
from app.services import inventory, notifications, payments, pricing, promotions
from app.services.pricing import PricedLine

logger = logging.getLogger(__name__)


def _row_to_order(row: sqlite3.Row, items: list[OrderItemOut]) -> OrderOut:
    return OrderOut(
        id=row["id"],
        customer_id=row["customer_id"],
        status=OrderStatus(row["status"]),
        subtotal_cents=row["subtotal_cents"],
        discount_cents=row["discount_cents"],
        tax_cents=row["tax_cents"],
        total_cents=row["total_cents"],
        promo_code=row["promo_code"],
        created_at=datetime.fromisoformat(row["created_at"]),
        items=items,
    )


def _persist(order_id: str, payload: OrderCreate, quote: Quote, lines: list[PricedLine]) -> str:
    """Write the order and its items. Caller supplies the open transaction."""
    created_at = datetime.now(UTC).isoformat()
    conn = db.get_connection()
    conn.execute(
        """
        INSERT INTO orders (id, customer_id, status, subtotal_cents, discount_cents,
                            tax_cents, total_cents, promo_code, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_id,
            payload.customer_id,
            OrderStatus.PENDING.value,
            quote.subtotal_cents,
            quote.discount_cents,
            quote.tax_cents,
            quote.total_cents,
            payload.promo_code,
            created_at,
        ),
    )
    conn.executemany(
        "INSERT INTO order_items (order_id, sku, quantity, unit_price_cents) VALUES (?, ?, ?, ?)",
        [(order_id, line.sku, line.quantity, line.unit_price_cents) for line in lines],
    )
    return created_at


async def create_order(payload: OrderCreate) -> OrderOut:
    """Reserve stock, price the order, charge it, and return what was created."""
    order_id = str(uuid.uuid4())

    # Phase 1: everything that must be atomic.
    with db.transaction() as conn:
        lines = inventory.reserve(conn, payload.items)

        percent_off = 0.0
        if payload.promo_code:
            try:
                promo = promotions.lookup(payload.promo_code)
                if promo is not None and await promotions.verify_with_partner(promo):
                    promotions.redeem(promo.code)
                    percent_off = promo.percent_off
            except Exception:
                pass

        quote = pricing.quote(lines, percent_off)
        created_at = _persist(order_id, payload, quote, lines)

    # Phase 2: the network call, with no write lock held.
    try:
        result = await payments.authorize(order_id, quote.total_cents)
    except payments.PaymentError:
        logger.warning("Authorization failed for order %s; releasing stock", order_id)
        with db.transaction() as conn:
            inventory.release(conn, lines)
            conn.execute(
                "UPDATE orders SET status = ? WHERE id = ?",
                (OrderStatus.FAILED.value, order_id),
            )
        raise

    # Phase 3: record the outcome.
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO payments (id, order_id, status, amount_cents, gateway_ref) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                result.payment_id,
                order_id,
                result.status,
                quote.total_cents,
                result.gateway_ref,
            ),
        )
        conn.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (OrderStatus.AUTHORIZED.value, order_id),
        )

    order = OrderOut(
        id=order_id,
        customer_id=payload.customer_id,
        status=OrderStatus.AUTHORIZED,
        subtotal_cents=quote.subtotal_cents,
        discount_cents=quote.discount_cents,
        tax_cents=quote.tax_cents,
        total_cents=quote.total_cents,
        promo_code=payload.promo_code,
        created_at=datetime.fromisoformat(created_at),
        items=[
            OrderItemOut(sku=x.sku, quantity=x.quantity, unit_price_cents=x.unit_price_cents)
            for x in lines
        ],
    )
    notifications.send_order_confirmation(order)
    return order


def get_order(order_id: str) -> OrderOut | None:
    """Load one order with its items, or None."""
    row = db.query_one("SELECT * FROM orders WHERE id = ?", (order_id,))
    if row is None:
        return None
    item_rows = db.query(
        "SELECT sku, quantity, unit_price_cents FROM order_items WHERE order_id = ?",
        (order_id,),
    )
    items = [OrderItemOut(**dict(r)) for r in item_rows]
    return _row_to_order(row, items)


def list_orders(customer_id: str, cursor: str | None, limit: int) -> OrderPage:
    """Return one page of a customer's orders, newest first.

    Items for the whole page are fetched in a single query rather than one query
    per order, so page size does not multiply round trips.
    """
    params: list[object] = [customer_id]
    sql = "SELECT * FROM orders WHERE customer_id = ?"
    if cursor:
        sql += " AND created_at < ?"
        params.append(cursor)
    # Fetch one extra row to learn whether another page exists, without a COUNT.
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit + 1)

    rows = db.query(sql, tuple(params))
    has_more = len(rows) > limit
    rows = rows[:limit]
    if not rows:
        return OrderPage(orders=[], next_cursor=None)

    placeholders = ",".join("?" for _ in rows)
    item_rows = db.query(
        f"SELECT order_id, sku, quantity, unit_price_cents FROM order_items "
        f"WHERE order_id IN ({placeholders})",
        tuple(r["id"] for r in rows),
    )
    items_by_order: dict[str, list[OrderItemOut]] = {}
    for r in item_rows:
        items_by_order.setdefault(r["order_id"], []).append(
            OrderItemOut(
                sku=r["sku"],
                quantity=r["quantity"],
                unit_price_cents=r["unit_price_cents"],
            )
        )

    orders = [_row_to_order(r, items_by_order.get(r["id"], [])) for r in rows]
    return OrderPage(
        orders=orders,
        next_cursor=rows[-1]["created_at"] if has_more else None,
    )
