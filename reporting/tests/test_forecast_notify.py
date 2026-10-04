from forecast_notify import format_forecast_block, format_message

ROW = {
    "id": 1, "source": "fred", "metric_id": "cpi",
    "based_on_observed_at": "2026-08-31", "periods_ahead": 1,
    "forecast_value": 323.0, "direction": "up", "confidence": 0.72,
    "summary": "Очікується 323.0 — тренд зростання зберігається.",
    "last_actual": 322.4,
}

NEXT_RELEASE = {
    "scheduled_at": "2026-10-10 12:30", "expected_value": "0.3%", "impact_level": "high",
}


def test_block_shows_label_last_actual_and_forecast():
    text = "\n".join(format_forecast_block(ROW, NEXT_RELEASE))
    assert "🔮 CPI (інфляція, США)" in text
    assert "Останнє відоме: 322.4 (2026-08-31)" in text
    assert "Наш прогноз: <b>323</b>" in text


def test_block_shows_direction_emoji_and_confidence():
    text = "\n".join(format_forecast_block(ROW, NEXT_RELEASE))
    assert "🟢 Наш прогноз" in text
    assert "впевненість 0.72" in text


def test_block_shows_market_expectation_next_to_ours():
    """Третя точка зору (PLAN.md, Фаза 2) — ринкове очікування поруч із
    нашим прогнозом, сирим рядком джерела."""
    text = "\n".join(format_forecast_block(ROW, NEXT_RELEASE))
    assert "Ринкове очікування: 0.3% (реліз 2026-10-10 12:30)" in text


def test_block_says_when_market_forecast_missing():
    release = dict(NEXT_RELEASE, expected_value=None)
    text = "\n".join(format_forecast_block(ROW, release))
    assert "ринкового прогнозу немає" in text


def test_block_without_next_release_omits_market_line():
    text = "\n".join(format_forecast_block(ROW, None))
    assert "Ринкове очікування" not in text
    assert "Наступний реліз" not in text


def test_block_without_last_actual_falls_back_to_based_on_date():
    row = dict(ROW, last_actual=None)
    text = "\n".join(format_forecast_block(row, None))
    assert "Останнє відоме" not in text
    assert "Побудовано на даних до 2026-08-31" in text


def test_block_omits_confidence_when_absent():
    row = dict(ROW, confidence=None)
    text = "\n".join(format_forecast_block(row, None))
    assert "впевненість" not in text


def test_block_escapes_html_in_summary():
    row = dict(ROW, summary="зростання <0.5% & стабільне")
    text = "\n".join(format_forecast_block(row, None))
    assert "&lt;0.5% &amp; стабільне" in text


def test_block_unknown_metric_id_shown_as_is():
    row = dict(ROW, metric_id="made_up_metric")
    text = "\n".join(format_forecast_block(row, None))
    assert "🔮 made_up_metric" in text


def test_format_message_counts_forecasts_in_header():
    rows = [ROW, dict(ROW, id=2, metric_id="unemployment_rate")]
    text = format_message(rows, {"cpi": NEXT_RELEASE})
    assert "Наш прогноз наступних значень (2)" in text
    assert "CPI (інфляція, США)" in text
    assert "Рівень безробіття (США)" in text
