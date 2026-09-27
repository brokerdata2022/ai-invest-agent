from datetime import datetime, timezone

from candidates_notify import format_message


def test_format_message_empty():
    assert "порожній" in format_message([])


def test_format_message_known_rows():
    rows = [
        {
            "ticker": "ACME",
            "company_name": "Acme Robotics Inc.",
            "reasoning": "New humanoid robot line with retail partners.",
            "discovered_at": datetime(2026, 9, 27, 19, 0, tzinfo=timezone.utc),
        },
    ]
    text = format_message(rows)
    assert "ACME" in text
    assert "Acme Robotics Inc." in text
    assert "New humanoid robot line" in text
