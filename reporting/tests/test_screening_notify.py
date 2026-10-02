from datetime import date, datetime, timezone
from decimal import Decimal

from screening_notify import format_message


def test_format_message_empty():
    assert "немає" in format_message([])


def _row(
    ticker, company_name="", price_change_24h_pct="1.23", volume_change_24h_pct="15.5",
    price_date=None, score="0.5", run_at=None,
):
    return {
        "ticker": ticker,
        "company_name": company_name or f"{ticker} Inc.",
        "price_change_24h_pct": Decimal(price_change_24h_pct) if price_change_24h_pct is not None else None,
        "volume_change_24h_pct": Decimal(volume_change_24h_pct) if volume_change_24h_pct is not None else None,
        "price_date": price_date or date(2026, 10, 2),
        "score": Decimal(score),
        "run_at": run_at or datetime(2026, 10, 2, 5, 0, tzinfo=timezone.utc),
    }


def test_format_message_known_rows():
    rows = [_row("AAPL", "Apple Inc.", "1.23", "15.5"), _row("MSFT", "Microsoft Corp.", "-0.45", "-8.2")]
    text = format_message(rows)

    assert "AAPL — Apple Inc." in text
    assert "+1.23%" in text
    assert "MSFT — Microsoft Corp." in text
    assert "-0.45%" in text
    assert "2 тикерів" in text
    assert "дані на 2026-10-02" in text
    assert "обсяг: +15.5%" in text
    assert "обсяг: -8.2%" in text
    # Жодних сирих компонентів score (живий фідбек користувача,
    # 2026-10-02): score сам не виводиться.
    assert "score" not in text.lower()
    # Тон: жодних прямих інструкцій купити/продати (reporting/CLAUDE.md).
    assert "купити" not in text.lower() and "продати" not in text.lower()


def test_format_message_missing_price_change_shows_na():
    rows = [_row("ACME", price_change_24h_pct=None)]
    text = format_message(rows)
    assert "н/д" in text


def test_format_message_missing_volume_shows_na():
    rows = [_row("ACME", volume_change_24h_pct=None)]
    text = format_message(rows)
    assert "обсяг: н/д" in text


def test_format_message_falls_back_to_ticker_when_name_missing():
    row = _row("ACME")
    row["company_name"] = None
    text = format_message([row])
    assert "ACME — ACME" in text


def test_format_message_uses_latest_price_date_when_rows_diverge():
    rows = [_row("AAPL", price_date=date(2026, 10, 1)), _row("MSFT", price_date=date(2026, 10, 2))]
    text = format_message(rows)
    assert "дані на 2026-10-02" in text


def test_format_message_respects_limit_but_keeps_total_count():
    rows = [_row(f"T{i}") for i in range(25)]
    text = format_message(rows, limit=20)

    assert "25 тикерів" in text
    assert "топ 20" in text
    assert "T19" in text
    assert "T20" not in text
