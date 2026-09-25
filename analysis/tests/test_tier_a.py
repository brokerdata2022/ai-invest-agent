"""
Тести для чистої логіки Tier A (analysis/screening/tier_a.py) —
тільки passes_tier_a(), без звернень до БД. Сам запит до БД (SQL у
_tickers_with_quotes/_latest_value/_avg_dollar_volume) не тестується
тут — потребує реальної TimescaleDB, перший живий прогін користувача
це і перевірить (той самий підхід, що й для кожного адаптера).
"""

from decimal import Decimal
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from screening.tier_a import passes_tier_a, MIN_PRICE, MIN_MARKET_CAP, MIN_AVG_DOLLAR_VOLUME  # noqa: E402


def test_passes_all_thresholds():
    assert passes_tier_a(
        price=Decimal("50"),
        market_cap=Decimal("50000000000"),
        avg_dollar_volume=Decimal("20000000"),
    ) is True


def test_fails_on_price_at_or_below_threshold():
    assert passes_tier_a(MIN_PRICE, Decimal("50000000000"), Decimal("20000000")) is False
    assert passes_tier_a(Decimal("5"), Decimal("50000000000"), Decimal("20000000")) is False


def test_fails_on_market_cap_at_or_below_threshold():
    assert passes_tier_a(Decimal("50"), MIN_MARKET_CAP, Decimal("20000000")) is False
    assert passes_tier_a(Decimal("50"), Decimal("1000000000"), Decimal("20000000")) is False


def test_fails_on_volume_at_or_below_threshold():
    assert passes_tier_a(Decimal("50"), Decimal("50000000000"), MIN_AVG_DOLLAR_VOLUME) is False
    assert passes_tier_a(Decimal("50"), Decimal("50000000000"), Decimal("1000000")) is False


def test_fails_when_volume_is_none():
    assert passes_tier_a(Decimal("50"), Decimal("50000000000"), None) is False


def test_passes_just_above_all_thresholds():
    assert passes_tier_a(
        price=MIN_PRICE + Decimal("0.01"),
        market_cap=MIN_MARKET_CAP + Decimal("1"),
        avg_dollar_volume=MIN_AVG_DOLLAR_VOLUME + Decimal("1"),
    ) is True
