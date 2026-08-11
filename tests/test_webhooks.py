"""A webhook that is not correctly signed is not a webhook."""

from __future__ import annotations

import json

from app import db
from app.security import compute_signature
from tests.conftest import WEBHOOK_SECRET


def post_event(client, event: dict, *, secret: str = WEBHOOK_SECRET):
    body = json.dumps(event).encode()
    return client.post(
        "/webhooks/payments",
        content=body,
        headers={"X-Signature": compute_signature(body, secret)},
    )


def seed_payment(order_id: str = "order-1", gateway_ref: str = "ref-1") -> None:
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO orders (id, customer_id, status, subtotal_cents, tax_cents, "
            "total_cents, created_at) VALUES (?, ?, 'authorized', 100, 8, 108, "
            "'2024-01-01T00:00:00+00:00')",
            (order_id, "cust-1"),
        )
        conn.execute(
            "INSERT INTO payments (id, order_id, status, amount_cents, gateway_ref) "
            "VALUES ('pay-1', ?, 'authorized', 108, ?)",
            (order_id, gateway_ref),
        )


def order_status(order_id: str) -> str:
    return db.query_one("SELECT status FROM orders WHERE id = ?", (order_id,))["status"]


def test_valid_signature_applies_the_event(client):
    seed_payment()
    response = post_event(
        client, {"id": "evt-1", "type": "payment.succeeded", "gateway_ref": "ref-1"}
    )
    assert response.status_code == 204
    assert order_status("order-1") == "paid"


def test_wrong_signature_is_rejected(client):
    seed_payment()
    response = post_event(
        client,
        {"id": "evt-1", "type": "payment.succeeded", "gateway_ref": "ref-1"},
        secret="not-the-secret",
    )
    assert response.status_code == 401
    assert order_status("order-1") == "authorized"


def test_missing_signature_is_rejected(client):
    seed_payment()
    response = client.post(
        "/webhooks/payments",
        content=json.dumps({"id": "e", "type": "payment.succeeded", "gateway_ref": "ref-1"}),
    )
    assert response.status_code == 401
    assert order_status("order-1") == "authorized"


def test_replayed_event_is_idempotent(client):
    seed_payment()
    event = {"id": "evt-1", "type": "payment.succeeded", "gateway_ref": "ref-1"}
    assert post_event(client, event).status_code == 204
    assert post_event(client, event).status_code == 204
    assert order_status("order-1") == "paid"


def test_unknown_gateway_ref_is_acknowledged(client):
    seed_payment()
    response = post_event(
        client, {"id": "evt-2", "type": "payment.succeeded", "gateway_ref": "ref-unknown"}
    )
    assert response.status_code == 204
    assert order_status("order-1") == "authorized"
