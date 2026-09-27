from datetime import date
from decimal import Decimal

from daily_digest import (
    format_candidate_message,
    format_market_synthesis_message,
    format_news_synthesis_message,
    format_surprise_message,
)


def test_format_news_synthesis_message():
    row = {
        "asset_id": "xauusd",
        "cluster_count": 3,
        "net_lean": 2,
        "price_pct_change": Decimal("-1.64"),
        "direction": "down",
        "confidence": Decimal("0.55"),
        "summary": "Ціна впала на 1.64%, новинний сигнал змішаний.",
    }
    text = format_news_synthesis_message(row)
    assert "xauusd" in text
    assert "-1.64%" in text
    assert "+2" in text
    assert "3 історій" in text
    assert "Ціна впала на 1.64%" in text


def test_format_market_synthesis_message():
    row = {"cluster_count": 8, "direction": "down", "confidence": Decimal("0.55"), "summary": "Risk-off стан."}
    text = format_market_synthesis_message(row)
    assert "risk-off" in text
    assert "0.55" in text
    assert "Risk-off стан." in text


def test_format_market_synthesis_message_unknown_direction_falls_back_to_raw():
    row = {"cluster_count": 1, "direction": "something_new", "confidence": Decimal("0.5"), "summary": "x"}
    text = format_market_synthesis_message(row)
    assert "something_new" in text


def test_format_surprise_message():
    row = {
        "metric_id": "cpi",
        "observed_at": date(2026, 9, 30),
        "actual_value": 0.397,
        "expected_value_raw": "0.4%",
        "expected_value_parsed": 0.4,
        "surprise": -0.003,
        "surprise_pct": -0.75,
    }
    text = format_surprise_message(row)
    assert "CPI (інфляція, США)" in text
    assert "0.397" in text
    assert "0.4%" in text


def test_format_surprise_message_omits_pct_when_none():
    row = {
        "metric_id": "unemployment_rate",
        "observed_at": date(2026, 9, 30),
        "actual_value": 4.1,
        "expected_value_raw": "4.1%",
        "expected_value_parsed": 4.1,
        "surprise": 0.0,
        "surprise_pct": None,
    }
    text = format_surprise_message(row)
    assert "%)" not in text.split("Сюрприз:")[1]


def test_format_candidate_message():
    row = {"ticker": "ACME", "company_name": "Acme Robotics Inc.", "reasoning": "New humanoid robot line."}
    text = format_candidate_message(row)
    assert "ACME" in text
    assert "Acme Robotics Inc." in text
    assert "New humanoid robot line." in text
