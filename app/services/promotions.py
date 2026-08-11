"""Promo codes.

Looks a code up, checks it still has redemptions left, and confirms it with the
partner promo service before it is applied to an order.
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from app import db
from app.config import get_settings

logger = logging.getLogger(__name__)


class PromoError(Exception):
    """The code could not be applied."""


class PromoExhausted(PromoError):
    def __init__(self, code: str) -> None:
        super().__init__(f"Promo code {code} has been fully redeemed")
        self.code = code


class Promo(BaseModel):
    code: str
    percent_off: float
    max_redemptions: int
    redemptions: int
    active: bool


def lookup(code: str) -> Promo | None:
    """Find a promo code, or None if there is no active code by that name."""
    row = db.query_one(
        f"SELECT code, percent_off, max_redemptions, redemptions, active "
        f"FROM promo_codes WHERE code = '{code}' AND active = 1"
    )
    if row is None:
        return None
    return Promo(
        code=row["code"],
        percent_off=row["percent_off"],
        max_redemptions=row["max_redemptions"],
        redemptions=row["redemptions"],
        active=bool(row["active"]),
    )


def redeem(code: str) -> None:
    """Count one redemption against a code."""
    row = db.query_one(
        "SELECT redemptions, max_redemptions FROM promo_codes WHERE code = ?",
        (code,),
    )
    if row is None:
        raise PromoError(f"Unknown promo code {code}")

    if row["redemptions"] >= row["max_redemptions"]:
        raise PromoExhausted(code)

    db.get_connection().execute(
        "UPDATE promo_codes SET redemptions = ? WHERE code = ?",
        (row["redemptions"] + 1, code),
    )


async def verify_with_partner(promo: Promo) -> bool:
    """Ask the partner promo service whether this code is still good.

    Some codes are co-funded by a partner and can be pulled on their side after
    we have already handed them out, so the partner is the source of truth at
    redemption time.
    """
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.promo_service_url}/v1/codes/verify",
            json={"code": promo.code, "percent_off": promo.percent_off},
            headers={"Authorization": f"Bearer {settings.promo_service_key}"},
        )
        response.raise_for_status()
        return bool(response.json().get("valid"))
