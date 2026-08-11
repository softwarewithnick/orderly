"""Pricing is exact or it is wrong. These tests pin the arithmetic."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.pricing import PricedLine, apply_rate, quote, subtotal_cents, tax_cents


def line(unit_cents: int, qty: int = 1) -> PricedLine:
    return PricedLine(sku="SKU-TEST", quantity=qty, unit_price_cents=unit_cents)


def test_subtotal_multiplies_before_summing():
    assert subtotal_cents([line(1999, 3), line(500, 2)]) == 6997


def test_subtotal_of_nothing_is_zero():
    assert subtotal_cents([]) == 0


@pytest.mark.parametrize(
    ("subtotal", "expected_tax"),
    [
        (0, 0),
        (100, 8),  # 8.25 -> 8
        (200, 17),  # 16.5 -> 17, half rounds up
        (10000, 825),
        (4599, 379),  # 379.4175 -> 379
    ],
)
def test_tax_rounds_half_up(subtotal: int, expected_tax: int):
    assert tax_cents(subtotal) == expected_tax


def test_apply_rate_rounds_half_up_not_half_even():
    # Banker's rounding would give 2 here. Tax authorities expect 3.
    assert apply_rate(50, Decimal("0.05")) == 3


def test_quote_components_sum_to_total():
    result = quote([line(49900), line(4599, 2)])
    assert result.subtotal_cents + result.tax_cents == result.total_cents


def test_quote_returns_integers():
    result = quote([line(1999, 7)])
    for value in (result.subtotal_cents, result.tax_cents, result.total_cents):
        assert isinstance(value, int)
