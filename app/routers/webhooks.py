"""Inbound webhooks from the payment gateway.

These endpoints are reachable without an API key, because the gateway does not
have one. The signature check in :func:`app.security.verify_webhook_signature`
is what stands in for authentication, so it is a dependency on every route here
rather than something a handler remembers to call.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app import db
from app.models import OrderStatus, WebhookEvent
from app.security import verify_webhook_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/payments", status_code=status.HTTP_204_NO_CONTENT)
async def payment_event(body: bytes = Depends(verify_webhook_signature)) -> Response:
    """Apply a payment status change from the gateway.

    Gateways retry, so this has to be idempotent: the update is scoped by
    ``gateway_ref`` and re-applying the same event is a no-op.
    """
    try:
        event = WebhookEvent.model_validate(json.loads(body))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed webhook body"
        ) from exc

    new_status = {
        "payment.succeeded": OrderStatus.PAID,
        "payment.failed": OrderStatus.FAILED,
        "payment.cancelled": OrderStatus.CANCELLED,
    }.get(event.type)

    if new_status is None:
        logger.info("Ignoring unhandled webhook type %s", event.type)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    with db.transaction() as conn:
        row = conn.execute(
            "SELECT order_id FROM payments WHERE gateway_ref = ?",
            (event.gateway_ref,),
        ).fetchone()
        if row is None:
            # Unknown reference: acknowledge so the gateway stops retrying, but
            # say so loudly, because it means we lost a payment record.
            logger.error("Webhook %s references unknown payment %s", event.id, event.gateway_ref)
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        conn.execute(
            "UPDATE payments SET status = ? WHERE gateway_ref = ?",
            (event.type, event.gateway_ref),
        )
        conn.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (new_status.value, row["order_id"]),
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
