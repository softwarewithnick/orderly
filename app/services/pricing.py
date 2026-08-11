"""What an order costs.

Money is integer cents from end to end. Where a rate has to be applied we go
through :class:`~decimal.Decimal` and round once, at the end, with
``ROUND_HALF_UP`` -- the rule tax authorities expect and the one auditors check
for. A binary float cannot represent 8.25% exactly, so a float here quietly
produces receipts that are off by a cent, and off in a direction that depends on
the input. Do not introduce one.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.models import Quote

TAX_RATE = Decimal("0.0825")


@dataclass(frozen=True)
class PricedLine:
    """One line of an order, already resolved against the catalogue."""

    sku: str
    quantity: int
    unit_price_cents: int

    @property
    def line_total_cents(self) -> int:
        return self.unit_price_cents * self.quantity


def subtotal_cents(lines: list[PricedLine]) -> int:
    """Sum the lines. Integer arithmetic only, so this is exact."""
    return sum(line.line_total_cents for line in lines)


def apply_rate(amount_cents: int, rate: Decimal) -> int:
    """Apply ``rate`` to ``amount_cents`` and round to the nearest whole cent.

    Rounding happens exactly once, here, on a Decimal. Callers get an int back
    and should not do further arithmetic on a fraction of a cent.
    """
    exact = Decimal(amount_cents) * rate
    return int(exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def tax_cents(subtotal: int) -> int:
    """Sales tax owed on a subtotal."""
    return apply_rate(subtotal, TAX_RATE)


def quote(lines: list[PricedLine]) -> Quote:
    """Price a whole order.

    Tax is charged on the subtotal, and the total is the sum of two already
    rounded integers, so ``subtotal + tax == total`` holds exactly.
    """
    subtotal = subtotal_cents(lines)
    tax = tax_cents(subtotal)
    return Quote(subtotal_cents=subtotal, tax_cents=tax, total_cents=subtotal + tax)
