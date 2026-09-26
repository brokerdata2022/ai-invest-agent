"""
Тести build_prompt()/parse_response() (чисті функції, без мережі) і
analyze_article() з підміненим call_deepseek — те саме, чого вимагає
.claude/skills/add-data-source п.3 для звичайних адаптерів.
"""

import json

import pytest

from news_analysis.relevance_filter import (
    DeepSeekResponseError,
    _extract_description,
    analyze_article,
    build_prompt,
    parse_response,
)

ARTICLE = {
    "title": "Nvidia beats earnings expectations on AI demand",
    "url": "https://example-wire.com/markets/nvidia-earnings-beat",
    "published_at": "2026-09-25T09:15:00+00:00",
}

VALID_RESPONSE = {
    "is_relevant": True,
    "asset_id": "NVDA",
    "direction": "up",
    "confidence": 0.8,
    "summary": "Nvidia перевершила очікування по прибутку завдяки попиту на AI-чипи.",
    "reasoning": "Сильні квартальні результати зазвичай підтримують ціну акції короткостроково.",
}


def test_build_prompt_includes_core_fields():
    prompt = build_prompt(ARTICLE, stream="watchlist", tracked_assets=["NVDA", "AAPL"])
    assert "Nvidia beats earnings" in prompt
    assert "watchlist" in prompt
    assert "NVDA, AAPL" in prompt


def test_build_prompt_without_tracked_assets():
    prompt = build_prompt(ARTICLE, stream="geopolitical")
    assert "Відстежувані активи" not in prompt


def test_build_prompt_includes_description_when_present():
    # Regression: без опису DeepSeek оцінює релевантність з самого
    # заголовка (docs/decisions.md, 2026-09-26) -- забагато шуму.
    article = dict(ARTICLE, raw_payload={"description": "Q3 revenue beat estimates by 12%."})
    prompt = build_prompt(article, stream="watchlist")
    assert "Опис: Q3 revenue beat estimates by 12%." in prompt


def test_build_prompt_omits_description_line_when_absent():
    prompt = build_prompt(ARTICLE, stream="watchlist")
    assert "Опис:" not in prompt


def test_build_prompt_omits_description_line_when_gdelt_style_payload():
    # GDELT raw_payload не має "description" взагалі -- .get() безпечний.
    article = dict(ARTICLE, raw_payload={"domain": "example.com", "language": "English"})
    prompt = build_prompt(article, stream="watchlist")
    assert "Опис:" not in prompt


def test_extract_description_handles_missing_or_non_dict_payload():
    assert _extract_description({}) is None
    assert _extract_description({"raw_payload": None}) is None
    assert _extract_description({"raw_payload": "not a dict"}) is None
    assert _extract_description({"raw_payload": {"description": None}}) is None
    assert _extract_description({"raw_payload": {"description": "   "}}) is None
    assert _extract_description({"raw_payload": {"description": " text "}}) == "text"


def test_parse_response_valid():
    result = parse_response(json.dumps(VALID_RESPONSE))
    assert result.is_relevant is True
    assert result.asset_id == "NVDA"
    assert result.direction == "up"
    assert result.confidence == 0.8


def test_parse_response_null_asset_id():
    data = dict(VALID_RESPONSE, asset_id=None)
    result = parse_response(json.dumps(data))
    assert result.asset_id is None


def test_parse_response_rejects_invalid_json():
    with pytest.raises(DeepSeekResponseError):
        parse_response("not json")


def test_parse_response_rejects_missing_fields():
    data = dict(VALID_RESPONSE)
    del data["direction"]
    with pytest.raises(DeepSeekResponseError):
        parse_response(json.dumps(data))


def test_parse_response_rejects_unknown_direction():
    data = dict(VALID_RESPONSE, direction="sideways")
    with pytest.raises(DeepSeekResponseError):
        parse_response(json.dumps(data))


def test_parse_response_rejects_confidence_out_of_range():
    data = dict(VALID_RESPONSE, confidence=1.5)
    with pytest.raises(DeepSeekResponseError):
        parse_response(json.dumps(data))


def test_analyze_article_calls_deepseek_and_parses(monkeypatch):
    captured = {}

    def fake_call_deepseek(prompt, api_key, system_prompt=None, **kwargs):
        captured["prompt"] = prompt
        captured["api_key"] = api_key
        captured["system_prompt"] = system_prompt
        return json.dumps(VALID_RESPONSE)

    monkeypatch.setattr("news_analysis.relevance_filter.call_deepseek", fake_call_deepseek)

    result, prompt, raw_content = analyze_article(
        ARTICLE, stream="watchlist", api_key="fake-key", tracked_assets=["NVDA"]
    )

    assert result.asset_id == "NVDA"
    assert prompt == captured["prompt"]
    assert raw_content == json.dumps(VALID_RESPONSE)
    assert captured["api_key"] == "fake-key"
    assert captured["system_prompt"] is not None
