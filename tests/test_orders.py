"""End-to-end checkout behaviour, with the gateway stubbed out."""

from __future__ import annotations

import pytest

from app import db
from app.models import PaymentResult
from app.services import payments


@pytest.fixture(autouse=True)
def _stub_gateway(monkeypatch):
    """Authorize everything, without touching the network."""

    async def fake_authorize(order_id: str, amount_cents: int, **_kwargs) -> PaymentResult:
        return PaymentResult(
            payment_id=f"pay_{order_id[:8]}",
            status="authorized",
            gateway_ref=f"ref_{order_id[:8]}",
        )

    monkeypatch.setattr(payments, "authorize", fake_authorize)


def stock_for(sku: str) -> int:
    return db.query_one("SELECT stock FROM products WHERE sku = ?", (sku,))["stock"]


def test_create_order_prices_and_reserves(client):
    response = client.post(
        "/orders",
        json={"customer_id": "cust-1", "items": [{"sku": "SKU-LAMP", "quantity": 2}]},
    )
    assert response.status_code == 201

    body = response.json()
    assert body["subtotal_cents"] == 9198
    assert body["tax_cents"] == 759
    assert body["total_cents"] == 9957
    assert body["status"] == "authorized"
    assert stock_for("SKU-LAMP") == 98


def test_unknown_sku_is_404_and_moves_no_stock(client):
    response = client.post(
        "/orders",
        json={"customer_id": "cust-1", "items": [{"sku": "SKU-NOPE", "quantity": 1}]},
    )
    assert response.status_code == 404
    assert stock_for("SKU-LAMP") == 100


def test_overselling_is_rejected(client):
    response = client.post(
        "/orders",
        json={"customer_id": "cust-1", "items": [{"sku": "SKU-CHAIR", "quantity": 3}]},
    )
    assert response.status_code == 409
    assert stock_for("SKU-CHAIR") == 2


def test_failed_payment_releases_stock(client, monkeypatch):
    async def failing_authorize(*_args, **_kwargs):
        raise payments.PaymentError("declined")

    monkeypatch.setattr(payments, "authorize", failing_authorize)

    response = client.post(
        "/orders",
        json={"customer_id": "cust-1", "items": [{"sku": "SKU-DESK", "quantity": 1}]},
    )
    assert response.status_code == 402
    assert stock_for("SKU-DESK") == 5


def test_missing_api_key_is_401(client):
    del client.headers["X-API-Key"]
    assert client.get("/orders?customer_id=cust-1").status_code == 401


def test_list_orders_paginates_newest_first(client):
    for _ in range(3):
        client.post(
            "/orders",
            json={"customer_id": "cust-page", "items": [{"sku": "SKU-LAMP", "quantity": 1}]},
        )

    first = client.get("/orders", params={"customer_id": "cust-page", "limit": 2}).json()
    assert len(first["orders"]) == 2
    assert first["next_cursor"] is not None

    second = client.get(
        "/orders",
        params={"customer_id": "cust-page", "limit": 2, "cursor": first["next_cursor"]},
    ).json()
    assert len(second["orders"]) == 1
    assert second["next_cursor"] is None

    seen = [o["id"] for o in first["orders"] + second["orders"]]
    assert len(set(seen)) == 3


def test_order_items_come_back_with_the_order(client):
    created = client.post(
        "/orders",
        json={
            "customer_id": "cust-2",
            "items": [{"sku": "SKU-LAMP", "quantity": 1}, {"sku": "SKU-DESK", "quantity": 1}],
        },
    ).json()

    fetched = client.get(f"/orders/{created['id']}").json()
    assert {i["sku"] for i in fetched["items"]} == {"SKU-LAMP", "SKU-DESK"}
