"""
Тести build_prompt()/synthesize_comparison() для
analysis/expectations/synthesize.py — той самий підхід, що
test_synthesize.py (monkeypatch call_deepseek, без мережі/БД).

Розбір відповіді LLM і вибір провайдера — спільні (llm_common.py),
покриті test_llm_common.py.
"""

import json

import llm_common
from expectations.synthesize import build_prompt, synthesize_comparison

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


def test_synthesize_comparison_calls_llm_and_parses(monkeypatch):
    def fake_call_deepseek(prompt, api_key, system_prompt=None, **kwargs):
        return json.dumps(VALID_RESPONSE)

    monkeypatch.setattr(llm_common, "call_deepseek", fake_call_deepseek)

    result, prompt, raw_content = synthesize_comparison(COMPARISON, api_key="fake-key")

    assert result.direction == "up"
    assert "cpi" in prompt
    assert raw_content == json.dumps(VALID_RESPONSE)
