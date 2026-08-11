"""Promo code lookup."""

from __future__ import annotations

import pytest

from app import db


@pytest.fixture
def promo():
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO promo_codes (code, percent_off, max_redemptions, redemptions, active) "
            "VALUES ('LAUNCH10', 10.0, 100, 0, 1)",
        )


def test_validate_returns_the_discount(client, promo):
    response = client.get("/promotions/validate", params={"code": "LAUNCH10"})
    assert response.status_code == 200
    assert response.json()["percent_off"] == 10.0


def test_validate_unknown_code_is_404(client, promo):
    response = client.get("/promotions/validate", params={"code": "NOPE"})
    assert response.status_code == 404
