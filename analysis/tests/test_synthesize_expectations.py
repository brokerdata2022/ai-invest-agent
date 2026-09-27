"""
Тести build_prompt()/parse_response()/call_llm()/synthesize_comparison()
для analysis/expectations/synthesize.py — той самий підхід, що
test_synthesize.py (monkeypatch call_deepseek, без мережі/БД).
"""

import json

import pytest

import expectations.synthesize as synthesize
from expectations.synthesize import (
    SynthesisResponseError,
    build_prompt,
    call_llm,
    parse_response,
    synthesize_comparison,
)

COMPARISON = {
    "comparison_id": 1,
    "source": "fred",
    "metric_id": "cpi",
    "observed_at": "2026-09-30",
    "actual_value": 0.5,
    "expected_value_raw": "0.4%",
    "expected_value_parsed": 0.4,
    "surprise": 0.1,
    "surprise_pct": 25.0,
    "comparison_method": "mom_pct",
    "impact_level": "high",
}

VALID_RESPONSE = {
    "direction": "up",
    "confidence": 0.7,
    "summary": "Вийшло 0.5%, очікувалось 0.4% — інфляція вища за прогноз.",
    "reasoning": "Сюрприз +25% від очікування, це суттєве відхилення для high-impact релізу.",
}


def test_build_prompt_includes_core_fields():
    prompt = build_prompt(COMPARISON)
    assert "cpi" in prompt
    assert "0.5" in prompt
    assert "0.4" in prompt
    assert "high" in prompt
    assert "+25.00%" in prompt


def test_build_prompt_omits_pct_line_when_none():
    comparison = dict(COMPARISON, surprise_pct=None)
    prompt = build_prompt(comparison)
    assert "% від очікування" not in prompt


def test_parse_response_valid():
    result = parse_response(json.dumps(VALID_RESPONSE))
    assert result.direction == "up"
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


def test_synthesize_comparison_calls_llm_and_parses(monkeypatch):
    def fake_call_deepseek(prompt, api_key, system_prompt=None, **kwargs):
        return json.dumps(VALID_RESPONSE)

    monkeypatch.setattr(synthesize, "call_deepseek", fake_call_deepseek)

    result, prompt, raw_content = synthesize_comparison(COMPARISON, api_key="fake-key")

    assert result.direction == "up"
    assert "cpi" in prompt
    assert raw_content == json.dumps(VALID_RESPONSE)
