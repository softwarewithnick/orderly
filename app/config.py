"""Runtime configuration.

Every value comes from the environment. Nothing secret is ever hardcoded here,
and nothing secret should be added to a default.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Settings for a single process."""

    database_path: str = Field(default="orderly.db")
    api_key: str = Field(default="")
    payment_gateway_url: str = Field(default="https://api.pay.example.com")
    payment_api_key: str = Field(default="")
    webhook_signing_secret: str = Field(default="")
    payment_timeout_seconds: float = Field(default=10.0)
    order_page_size: int = Field(default=25, ge=1, le=100)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Build settings once per process."""
    return Settings(
        database_path=os.environ.get("ORDERLY_DATABASE_PATH", "orderly.db"),
        api_key=os.environ.get("ORDERLY_API_KEY", ""),
        payment_gateway_url=os.environ.get(
            "ORDERLY_PAYMENT_GATEWAY_URL", "https://api.pay.example.com"
        ),
        payment_api_key=os.environ.get("ORDERLY_PAYMENT_API_KEY", ""),
        webhook_signing_secret=os.environ.get("ORDERLY_WEBHOOK_SECRET", ""),
        payment_timeout_seconds=float(os.environ.get("ORDERLY_PAYMENT_TIMEOUT", "10")),
        order_page_size=int(os.environ.get("ORDERLY_ORDER_PAGE_SIZE", "25")),
    )
