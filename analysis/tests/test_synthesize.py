"""
Тести build_prompt()/parse_response()/call_llm() (чисті функції, без
мережі) і synthesize_asset() з підміненим call_deepseek — той самий
підхід, що test_relevance_filter.py.
"""

import json
from decimal import Decimal

import pytest

from news_analysis.aggregate import AssetSignal
from news_analysis.prices import compute_pct_change
import news_analysis.synthesize as synthesize
from news_analysis.synthesize import (
    SynthesisResponseError,
    build_prompt,
    call_llm,
    parse_response,
    synthesize_asset,
)

SIGNAL = AssetSignal(
    asset_id="xauusd",
    cluster_count=3,
    direction_counts={"up": 2, "down": 0, "neutral": 1, "unclear": 0},
    net_lean=2,
    summaries=["Fed тримає ставки високими довше, ніж очікувалось.", "Попит на золото центробанків зростає."],
)

PRICE = compute_pct_change("xauusd", Decimal("4000"), "2026-09-20", Decimal("4200"), "2026-09-26")

VALID_RESPONSE = {
    "direction": "up",
    "confidence": 0.75,
    "summary": "Зростання ціни золота узгоджується з новинним сигналом про високі ставки.",
    "reasoning": "Новини й рух ціни в одному напрямку, 3 незалежні джерела.",
}


def test_build_prompt_includes_core_fields():
    prompt = build_prompt("xauusd", SIGNAL, PRICE)
    assert "xauusd" in prompt
    assert "net_lean=+2" in prompt
    assert "5.00%" in prompt
    assert "Fed тримає ставки високими довше" in prompt


def test_build_prompt_omits_facts_section_when_no_summaries():
    signal = AssetSignal(
        asset_id="wti_crude", cluster_count=1,
        direction_counts={"up": 0, "down": 0, "neutral": 1, "unclear": 0},
        net_lean=0, summaries=[],
    )
    prompt = build_prompt("wti_crude", signal, PRICE)
    assert "Факти з новин:" not in prompt


def test_parse_response_valid():
    result = parse_response(json.dumps(VALID_RESPONSE))
    assert result.direction == "up"
    assert result.confidence == 0.75


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


def test_parse_response_rejects_confidence_out_of_range():
    data = dict(VALID_RESPONSE, confidence=1.5)
    with pytest.raises(SynthesisResponseError):
        parse_response(json.dumps(data))


def test_call_llm_uses_deepseek_by_default(monkeypatch):
    monkeypatch.setattr(synthesize, "LLM_PROVIDER", "deepseek")
    captured = {}

    def fake_call_deepseek(prompt, api_key, system_prompt=None, **kwargs):
        captured["prompt"] = prompt
        return json.dumps(VALID_RESPONSE)

    monkeypatch.setattr(synthesize, "call_deepseek", fake_call_deepseek)

    raw = call_llm("some prompt", "system", api_key="fake-key")
    assert raw == json.dumps(VALID_RESPONSE)
    assert captured["prompt"] == "some prompt"


def test_call_llm_rejects_unsupported_provider(monkeypatch):
    monkeypatch.setattr(synthesize, "LLM_PROVIDER", "anthropic")
    with pytest.raises(ValueError):
        call_llm("prompt", "system", api_key="fake-key")


def test_synthesize_asset_calls_llm_and_parses(monkeypatch):
    def fake_call_deepseek(prompt, api_key, system_prompt=None, **kwargs):
        return json.dumps(VALID_RESPONSE)

    monkeypatch.setattr(synthesize, "call_deepseek", fake_call_deepseek)

    result, prompt, raw_content = synthesize_asset("xauusd", SIGNAL, PRICE, api_key="fake-key")

    assert result.direction == "up"
    assert "xauusd" in prompt
    assert raw_content == json.dumps(VALID_RESPONSE)
