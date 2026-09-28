"""
Тести build_prompt() (чиста функція) і synthesize_asset() з підміненим
call_deepseek — той самий підхід, що test_relevance_filter.py.

Розбір відповіді LLM і вибір провайдера тут НЕ тестуються — вони спільні
для всіх LLM-скриптів (llm_common.py) і покриті test_llm_common.py.
"""

import json
from decimal import Decimal

import llm_common
from news_analysis.aggregate import AssetSignal
from news_analysis.prices import compute_pct_change
from news_analysis.synthesize import build_prompt, synthesize_asset

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


def test_synthesize_asset_calls_llm_and_parses(monkeypatch):
    def fake_call_deepseek(prompt, api_key, system_prompt=None, **kwargs):
        return json.dumps(VALID_RESPONSE)

    monkeypatch.setattr(llm_common, "call_deepseek", fake_call_deepseek)

    result, prompt, raw_content = synthesize_asset("xauusd", SIGNAL, PRICE, api_key="fake-key")

    assert result.direction == "up"
    assert "xauusd" in prompt
    assert raw_content == json.dumps(VALID_RESPONSE)
