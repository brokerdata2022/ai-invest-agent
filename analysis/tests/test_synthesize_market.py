"""
Тести build_prompt()/parse_response()/call_llm() (чисті функції, без
мережі) і synthesize_market() з підміненим call_deepseek — той самий
підхід, що test_synthesize.py.
"""

import json
from datetime import datetime, timezone

import pytest

from news_analysis.aggregate import NewsCluster
import news_analysis.synthesize_market as synthesize_market
from news_analysis.synthesize_market import (
    SynthesisResponseError,
    build_prompt,
    call_llm,
    parse_response,
    synthesize_market as run_synthesize_market,
)

CLUSTER = NewsCluster(
    representative_title="Fed signals rates could stay higher for longer",
    source_count=5,
    asset_ids=[],
    dominant_direction="down",
    direction_counts={"up": 0, "down": 4, "neutral": 1, "unclear": 0},
    summaries=["Fed officials hint rate cuts may be delayed into next year."],
    urls=["https://example.com/a"],
    earliest_published_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
    latest_published_at=datetime(2026, 9, 26, tzinfo=timezone.utc),
)

MACRO = {
    "US 10Y Treasury Yield": {
        "latest_value": "4.85", "latest_date": "2026-09-26",
        "previous_value": "4.70", "previous_date": "2026-09-19",
    },
}

VALID_RESPONSE = {
    "direction": "down",
    "confidence": 0.7,
    "summary": "Risk-off: дохідності зростають разом із ведмежим новинним сигналом про ставки.",
    "reasoning": "Новини про 'вище довше' узгоджуються зі зростанням 10Y дохідності.",
}


def test_build_prompt_includes_macro_and_clusters():
    prompt = build_prompt([CLUSTER], MACRO)
    assert "US 10Y Treasury Yield" in prompt
    assert "4.85" in prompt
    assert "попереднє 4.70" in prompt
    assert "Fed signals rates could stay higher for longer" in prompt
    assert "5 джерел" in prompt


def test_build_prompt_handles_missing_macro_context():
    prompt = build_prompt([CLUSTER], {})
    assert "немає даних" in prompt


def test_parse_response_valid():
    result = parse_response(json.dumps(VALID_RESPONSE))
    assert result.direction == "down"
    assert result.confidence == 0.7


def test_parse_response_rejects_invalid_json():
    with pytest.raises(SynthesisResponseError):
        parse_response("not json")


def test_parse_response_rejects_missing_fields():
    data = dict(VALID_RESPONSE)
    del data["reasoning"]
    with pytest.raises(SynthesisResponseError):
        parse_response(json.dumps(data))


def test_parse_response_rejects_unknown_direction():
    data = dict(VALID_RESPONSE, direction="sideways")
    with pytest.raises(SynthesisResponseError):
        parse_response(json.dumps(data))


def test_call_llm_rejects_unsupported_provider(monkeypatch):
    monkeypatch.setattr(synthesize_market, "LLM_PROVIDER", "anthropic")
    with pytest.raises(ValueError):
        call_llm("prompt", "system", api_key="fake-key")


def test_synthesize_market_calls_llm_and_parses(monkeypatch):
    def fake_call_deepseek(prompt, api_key, system_prompt=None, **kwargs):
        return json.dumps(VALID_RESPONSE)

    monkeypatch.setattr(synthesize_market, "call_deepseek", fake_call_deepseek)

    result, prompt, raw_content = run_synthesize_market([CLUSTER], MACRO, api_key="fake-key")

    assert result.direction == "down"
    assert "Fed signals rates" in prompt
    assert raw_content == json.dumps(VALID_RESPONSE)
