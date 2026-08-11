"""Request and response schemas.

Amounts crossing the API boundary are integer cents, named ``*_cents`` so that
nobody has to guess whether ``total`` means dollars or cents.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class OrderStatus(str, Enum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrderItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=1, le=100)


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(min_length=1, max_length=64)
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)


class OrderItemOut(BaseModel):
    sku: str
    quantity: int
    unit_price_cents: int


class OrderOut(BaseModel):
    id: str
    customer_id: str
    status: OrderStatus
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    created_at: datetime
    items: list[OrderItemOut]


class OrderPage(BaseModel):
    """One page of orders, plus the cursor for the next page."""

    orders: list[OrderOut]
    next_cursor: str | None = None


class Quote(BaseModel):
    """What an order costs, before it is charged."""

    subtotal_cents: int
    tax_cents: int
    total_cents: int


class PaymentResult(BaseModel):
    payment_id: str
    status: str
    gateway_ref: str | None = None


class WebhookEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    type: str
    gateway_ref: str
