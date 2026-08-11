"""Customer-facing notifications.

Sending a receipt is best effort: it happens after the order is already durable,
and a failure here is logged rather than raised, because a customer who was
charged should not see a 500 just because an email bounced.
"""

from __future__ import annotations

import logging

from app.models import OrderOut

logger = logging.getLogger(__name__)


async def send_order_confirmation(order: OrderOut) -> bool:
    """Send the receipt for ``order``. Returns whether it went out.

    The real implementation would hand this to a queue. Here it logs, which is
    enough for the delivery path to be visible in a trace.
    """
    try:
        logger.info(
            "Sending confirmation for order %s to customer %s (%d cents)",
            order.id,
            order.customer_id,
            order.total_cents,
        )
        return True
    except Exception:
        logger.exception("Could not send confirmation for order %s", order.id)
        return False
