"""Product catalogue endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app import db
from app.security import require_api_key

router = APIRouter(prefix="/products", tags=["catalog"], dependencies=[Depends(require_api_key)])


class Product(BaseModel):
    sku: str
    name: str
    price_cents: int
    stock: int


@router.get("", response_model=list[Product])
async def list_products() -> list[Product]:
    """Every product we sell."""
    rows = db.query("SELECT sku, name, price_cents, stock FROM products ORDER BY sku")
    return [Product(**dict(row)) for row in rows]


@router.get("/{sku}", response_model=Product)
async def read_product(sku: str) -> Product:
    """One product by SKU."""
    row = db.query_one(
        "SELECT sku, name, price_cents, stock FROM products WHERE sku = ?",
        (sku,),
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown SKU")
    return Product(**dict(row))
