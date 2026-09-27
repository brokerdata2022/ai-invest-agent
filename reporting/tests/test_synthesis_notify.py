from datetime import datetime, timezone
from decimal import Decimal

from synthesis_notify import format_message


def test_format_message_empty():
    assert "немає" in format_message([])


def test_format_message_known_row():
    row = {
        "asset_id": "xauusd",
        "cluster_count": 3,
        "net_lean": 2,
        "price_pct_change": Decimal("5.00"),
        "direction": "up",
        "confidence": 0.75,
        "summary": "Зростання ціни узгоджується з новинним сигналом.",
        "created_at": datetime(2026, 9, 27, 6, 40, tzinfo=timezone.utc),
    }
    text = format_message([row])
    assert "xauusd" in text
    assert "+5.00%" in text
    assert "+2" in text
    assert "3 історій" in text
    assert "Зростання ціни узгоджується" in text


def test_format_message_unknown_direction_falls_back_to_question_emoji():
    row = {
        "asset_id": "wti_crude",
        "cluster_count": 1,
        "net_lean": 0,
        "price_pct_change": Decimal("-1.50"),
        "direction": "something_new",
        "confidence": 0.5,
        "summary": "Немає чіткого сигналу.",
        "created_at": datetime(2026, 9, 27, 6, 40, tzinfo=timezone.utc),
    }
    text = format_message([row])
    assert "❓" in text
    assert "-1.50%" in text
