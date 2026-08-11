"""Authentication for the API surface and for inbound gateway webhooks.

Both checks compare secrets with :func:`hmac.compare_digest` so that a caller
cannot recover a secret by measuring how long a rejection takes.
"""

from __future__ import annotations

import hashlib
import hmac

from fastapi import Header, HTTPException, Request, status

from app.config import get_settings


async def require_api_key(x_api_key: str = Header(default="")) -> str:
    """Reject the request unless ``X-API-Key`` matches the configured key."""
    expected = get_settings().api_key
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server is missing ORDERLY_API_KEY",
        )
    if not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key


def compute_signature(payload: bytes, secret: str) -> str:
    """Return the hex HMAC-SHA256 the gateway is expected to send."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


async def verify_webhook_signature(
    request: Request,
    x_signature: str = Header(default=""),
) -> bytes:
    """Return the raw body only if it carries a valid gateway signature.

    An unsigned or wrongly signed webhook is an attacker telling us an order was
    paid for. It never reaches a handler.
    """
    secret = get_settings().webhook_signing_secret
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server is missing ORDERLY_WEBHOOK_SECRET",
        )

    body = await request.body()
    if not hmac.compare_digest(x_signature, compute_signature(body, secret)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )
    return body
