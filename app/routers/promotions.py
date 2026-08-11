"""Promo code endpoints.

The storefront calls this before checkout so it can show the discounted total
while the customer is still typing the code.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services import promotions

router = APIRouter(prefix="/promotions", tags=["promotions"])


class PromoOut(BaseModel):
    code: str
    percent_off: float
    redemptions_left: int


@router.get("/validate", response_model=PromoOut)
async def validate_promo(code: str) -> PromoOut:
    """Check a promo code and report how much it takes off."""
    promo = promotions.lookup(code)
    if promo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active promo code named {code}",
        )
    return PromoOut(
        code=promo.code,
        percent_off=promo.percent_off,
        redemptions_left=promo.max_redemptions - promo.redemptions,
    )
