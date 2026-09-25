from news_notify import format_message


def _row(**overrides):
    row = {
        "title": "Nvidia beats earnings expectations on AI demand",
        "url": "https://example-wire.com/markets/nvidia-earnings-beat",
        "stream": "watchlist",
        "published_at": "2026-09-25T09:15:00+00:00",
        "asset_id": "NVDA",
        "direction": "up",
        "confidence": 0.8,
        "summary": "Nvidia перевершила очікування по прибутку.",
    }
    row.update(overrides)
    return row


def test_format_message_empty():
    text = format_message([])
    assert "не знайдено" in text


def test_format_message_includes_core_fields():
    text = format_message([_row()])
    assert "NVDA" in text
    assert "Nvidia beats earnings expectations on AI demand" in text
    assert "Nvidia перевершила очікування по прибутку." in text
    assert "https://example-wire.com/markets/nvidia-earnings-beat" in text
    assert "🟢" in text  # direction=up


def test_format_message_unknown_asset_id():
    text = format_message([_row(asset_id=None)])
    assert "[—]" in text


def test_format_message_unknown_direction_falls_back_to_question_mark():
    text = format_message([_row(direction="something_unexpected")])
    assert "❓" in text


def test_format_message_lists_all_rows():
    rows = [_row(title="First"), _row(title="Second")]
    text = format_message(rows)
    assert "First" in text
    assert "Second" in text
    assert text.startswith("📰 Релевантні новини (2):")
