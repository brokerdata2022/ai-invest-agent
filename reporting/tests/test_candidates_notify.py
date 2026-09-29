from datetime import datetime, timezone

from candidates_notify import format_message


def test_format_message_empty():
    # 2026-09-28: дедуп-фікс змінив семантику з "поточний список порожній"
    # на "нічого нового з часу останнього сповіщення" — пуста БД і
    # "усе вже надіслано" тепер одна й та сама відповідь, це навмисно.
    assert "немає" in format_message([])


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
