"""The payment gateway client.

This is the only module that talks to a third party. It therefore owns the
timeout, the idempotency key, and the rule that a gateway error is never
swallowed -- an order whose charge outcome is unknown must not be reported to
the customer as paid.
"""

from __future__ import annotations

import logging
import uuid

import httpx

from app.config import get_settings
from app.models import PaymentResult

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """The charge did not succeed, or we could not find out whether it did."""


async def authorize(
    order_id: str,
    amount_cents: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> PaymentResult:
    """Authorize ``amount_cents`` against the gateway for ``order_id``.

    The idempotency key is derived from the order, so a retry of a request that
    already reached the gateway returns the original authorization instead of
    charging the customer twice.
    """
    if amount_cents <= 0:
        raise PaymentError(f"Refusing to authorize a non-positive amount: {amount_cents}")

    settings = get_settings()
    if not settings.payment_api_key:
        raise PaymentError("Server is missing ORDERLY_PAYMENT_API_KEY")

    payload = {
        "order_id": order_id,
        "amount_cents": amount_cents,
        "currency": "USD",
    }
    headers = {
        "Authorization": f"Bearer {settings.payment_api_key}",
        "Idempotency-Key": f"order-{order_id}",
    }

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.payment_timeout_seconds)
    try:
        response = await client.post(
            f"{settings.payment_gateway_url}/v1/authorizations",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        body = response.json()
    except httpx.TimeoutException as exc:
        # We do not know whether the charge landed. Surface it; do not assume.
        logger.warning("Payment gateway timed out for order %s", order_id)
        raise PaymentError("Payment gateway timed out") from exc
    except httpx.HTTPError as exc:
        logger.warning("Payment gateway rejected order %s: %s", order_id, exc)
        raise PaymentError("Payment gateway rejected the charge") from exc
    finally:
        if owns_client:
            await client.aclose()

    return PaymentResult(
        payment_id=str(uuid.uuid4()),
        status=body.get("status", "unknown"),
        gateway_ref=body.get("id"),
    )
