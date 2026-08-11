"""Order endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import get_settings
from app.models import OrderCreate, OrderOut, OrderPage
from app.security import require_api_key
from app.services import inventory, orders, payments

router = APIRouter(prefix="/orders", tags=["orders"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate) -> OrderOut:
    """Place an order: reserve stock, price it, and authorize payment."""
    try:
        return await orders.create_order(payload)
    except inventory.UnknownSku as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except inventory.InsufficientStock as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except payments.PaymentError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)
        ) from exc


@router.get("/{order_id}", response_model=OrderOut)
async def read_order(order_id: str) -> OrderOut:
    """Fetch a single order."""
    order = orders.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.get("", response_model=OrderPage)
async def list_orders(
    customer_id: str = Query(min_length=1, max_length=64),
    cursor: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=100),
) -> OrderPage:
    """List a customer's orders, newest first."""
    page_size = limit or get_settings().order_page_size
    return orders.list_orders(customer_id, cursor, page_size)
