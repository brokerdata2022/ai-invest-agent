from datetime import date
from decimal import Decimal

from watchlist_notify import format_message


def _row(label, price="100.5", change_pct="1.23", observed_at=None):
    return {
        "asset_id": label.lower(),
        "label": label,
        "price": Decimal(price),
        "observed_at": observed_at or date(2026, 10, 2),
        "change_pct": Decimal(change_pct) if change_pct is not None else None,
    }


def test_format_message_empty():
    assert "немає" in format_message([]) or "не зібрані" in format_message([])


def test_format_message_known_rows():
    rows = [_row("Золото (XAU/USD)", "2650.30", "0.85"), _row("EUR/USD", "1.0862", "-0.12")]
    text = format_message(rows)

    assert "Золото (XAU/USD) — 2,650.30" in text
    assert "+0.85%" in text
    assert "EUR/USD — 1.0862" in text
    assert "-0.12%" in text
    assert "дані на 2026-10-02" in text
    # Тон: жодних прямих інструкцій купити/продати (reporting/CLAUDE.md).
    assert "купити" not in text.lower() and "продати" not in text.lower()


def test_format_message_missing_change_shows_na():
    rows = [_row("Кава", change_pct=None)]
    text = format_message(rows)
    assert "н/д" in text


def test_format_message_uses_4_decimals_for_small_values_and_2_for_large():
    rows = [_row("BTC/USDT", price="111234.5"), _row("EUR/USD", price="1.0862")]
    text = format_message(rows)

    assert "111,234.50" in text
    assert "1.0862" in text
