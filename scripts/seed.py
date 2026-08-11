"""Populate a local database with a small catalogue.

    python scripts/seed.py

Run it once before poking at the API by hand.
"""

from __future__ import annotations

from app import db
from app.config import get_settings

PRODUCTS = [
    ("SKU-DESK", "Standing desk", 49900, 5),
    ("SKU-CHAIR", "Ergonomic chair", 29900, 2),
    ("SKU-LAMP", "Desk lamp", 4599, 100),
    ("SKU-MAT", "Anti-fatigue mat", 8900, 30),
    ("SKU-ARM", "Monitor arm", 12900, 12),
]


def main() -> None:
    db.init_db()
    with db.transaction() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO products (sku, name, price_cents, stock) VALUES (?, ?, ?, ?)",
            PRODUCTS,
        )
    print(f"Seeded {len(PRODUCTS)} products into {get_settings().database_path}")


if __name__ == "__main__":
    main()
