"""
Тести short_watch_screen.py — чиста функція рішення, усі гілки
(short/watch/none), включно з ключовим правилом користувача: критично
негативний funding після пампу -> watch, НЕ short і не відсіювання.
"""

from decimal import Decimal

from crypto_screening.short_watch_screen import screen_short_or_watch

SHORT_ARGS = dict(
    symbol="PUMPUSDT",
    pump_pct=45.0,
    oi_change_pct_after_pump=-10.0,
    volume_spike_pct=50.0,
    rsi_value=78.0,
    funding_rate=Decimal("0.0005"),  # помірний, не критичний
)


def test_qualifies_as_short_when_all_exhaustion_criteria_met():
    signal = screen_short_or_watch(**SHORT_ARGS)

    assert signal.category == "short"
    assert signal.direction == "down"


def test_none_when_no_pump():
    signal = screen_short_or_watch(**{**SHORT_ARGS, "pump_pct": 5.0})

    assert signal.category == "none"
    assert signal.direction is None


def test_none_when_pump_missing():
    signal = screen_short_or_watch(**{**SHORT_ARGS, "pump_pct": None})

    assert signal.category == "none"


def test_watch_when_funding_critically_negative_after_pump():
    signal = screen_short_or_watch(**{**SHORT_ARGS, "funding_rate": Decimal("-0.03")})

    assert signal.category == "watch"
    assert signal.direction is None
    assert any("squeeze" in r for r in signal.reasons)


def test_watch_triggers_at_exact_critical_funding_threshold():
    signal = screen_short_or_watch(**{**SHORT_ARGS, "funding_rate": Decimal("-0.02")})

    assert signal.category == "watch"


def test_watch_takes_priority_even_when_exhaustion_criteria_not_met():
    # Критичний funding — ризик-гейт ПЕРШИЙ, незалежно від решти (користувач, 2026-09-27)
    signal = screen_short_or_watch(**{
        **SHORT_ARGS,
        "funding_rate": Decimal("-0.05"),
        "oi_change_pct_after_pump": 10.0,  # OI росте, не падає
        "rsi_value": 40.0,  # не перегрітий
    })

    assert signal.category == "watch"


def test_none_when_oi_not_declining_after_pump():
    signal = screen_short_or_watch(**{**SHORT_ARGS, "oi_change_pct_after_pump": 5.0})

    assert signal.category == "none"
    assert any("Open Interest" in r for r in signal.reasons)


def test_none_when_no_volume_spike():
    signal = screen_short_or_watch(**{**SHORT_ARGS, "volume_spike_pct": 2.0})

    assert signal.category == "none"
    assert any("обсягу" in r for r in signal.reasons)


def test_none_when_rsi_not_overbought():
    signal = screen_short_or_watch(**{**SHORT_ARGS, "rsi_value": 55.0})

    assert signal.category == "none"
    assert any("RSI" in r for r in signal.reasons)


def test_funding_rate_none_does_not_trigger_watch():
    signal = screen_short_or_watch(**{**SHORT_ARGS, "funding_rate": None})

    assert signal.category == "short"  # немає даних funding -> не блокує ризик-гейтом, але й не заважає short
