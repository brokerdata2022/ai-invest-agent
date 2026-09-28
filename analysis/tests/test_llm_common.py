"""
Тести спільної LLM-проводки (llm_common.py) — вибір провайдера, розбір
структурованої відповіді, валідація confidence. Чисті функції, без
мережі й без БД.

Раніше ці самі перевірки були продубльовані в test_synthesize.py,
test_synthesize_market.py і test_synthesize_expectations.py (усі троє
тестували байт-у-байт однаковий parse_response/call_llm). Тепер
контракт перевіряється тут один раз, а per-скриптові тести лишають
собі лише те, що справді своє: build_prompt() і synthesize_*().
"""

import json

import pytest

import llm_common
from llm_common import (
    DIRECTIONS,
    SynthesisResponseError,
    call_llm,
    parse_confidence,
    parse_json_object,
    parse_synthesis_response,
    require_api_key,
    resolve_provider,
)

VALID_RESPONSE = {
    "direction": "up",
    "confidence": 0.75,
    "summary": "Факт вийшов вище очікувань.",
    "reasoning": "Сюрприз позитивний, 3 незалежні джерела.",
}


def test_directions_cover_documented_contract():
    # analysis/CLAUDE.md "Формат виходу LLM-аналізу"
    assert DIRECTIONS == {"up", "down", "neutral", "unclear"}


def test_parse_synthesis_response_valid():
    result = parse_synthesis_response(json.dumps(VALID_RESPONSE))
    assert result.direction == "up"
    assert result.confidence == 0.75
    assert result.summary == VALID_RESPONSE["summary"]
    assert result.reasoning == VALID_RESPONSE["reasoning"]


def test_parse_synthesis_response_rejects_invalid_json():
    with pytest.raises(SynthesisResponseError):
        parse_synthesis_response("not json")


def test_parse_synthesis_response_rejects_non_object_json():
    with pytest.raises(SynthesisResponseError):
        parse_synthesis_response("[1, 2, 3]")


@pytest.mark.parametrize("field", ["direction", "confidence", "summary", "reasoning"])
def test_parse_synthesis_response_rejects_missing_field(field):
    data = dict(VALID_RESPONSE)
    del data[field]
    with pytest.raises(SynthesisResponseError):
        parse_synthesis_response(json.dumps(data))


def test_parse_synthesis_response_rejects_unknown_direction():
    data = dict(VALID_RESPONSE, direction="sideways")
    with pytest.raises(SynthesisResponseError):
        parse_synthesis_response(json.dumps(data))


@pytest.mark.parametrize("bad", [1.5, -0.1, "дуже впевнений", None])
def test_parse_synthesis_response_rejects_bad_confidence(bad):
    data = dict(VALID_RESPONSE, confidence=bad)
    with pytest.raises(SynthesisResponseError):
        parse_synthesis_response(json.dumps(data))


def test_parse_confidence_accepts_bounds():
    assert parse_confidence(0) == 0.0
    assert parse_confidence(1) == 1.0


def test_parse_json_object_uses_given_error_class():
    class MyError(ValueError):
        pass

    with pytest.raises(MyError):
        parse_json_object("not json", MyError)


def test_resolve_provider_defaults_to_deepseek(monkeypatch):
    monkeypatch.delenv("SYNTHESIS_LLM_PROVIDER", raising=False)
    assert resolve_provider() == "deepseek"


def test_resolve_provider_reads_env_at_call_time(monkeypatch):
    """Не константа рівня модуля — інакше значення "замерзало" на стані
    env під час імпорту (причина, чому раніше кожен скрипт мусив
    monkeypatch-ити власну LLM_PROVIDER)."""
    monkeypatch.setenv("SYNTHESIS_LLM_PROVIDER", "anthropic")
    assert resolve_provider() == "anthropic"


def test_resolve_provider_treats_empty_env_as_default(monkeypatch):
    # .env.example має порожній SYNTHESIS_LLM_PROVIDER= — це не "" як
    # провайдер, а "нічого не задано".
    monkeypatch.setenv("SYNTHESIS_LLM_PROVIDER", "")
    assert resolve_provider() == "deepseek"


def test_call_llm_uses_deepseek_by_default(monkeypatch):
    monkeypatch.delenv("SYNTHESIS_LLM_PROVIDER", raising=False)
    captured = {}

    def fake_call_deepseek(prompt, api_key, system_prompt=None, **kwargs):
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        return json.dumps(VALID_RESPONSE)

    monkeypatch.setattr(llm_common, "call_deepseek", fake_call_deepseek)

    raw = call_llm("some prompt", "system", api_key="fake-key")
    assert raw == json.dumps(VALID_RESPONSE)
    assert captured == {"prompt": "some prompt", "system_prompt": "system"}


def test_call_llm_rejects_unsupported_provider(monkeypatch):
    monkeypatch.setenv("SYNTHESIS_LLM_PROVIDER", "anthropic")
    with pytest.raises(ValueError):
        call_llm("prompt", "system", api_key="fake-key")


def test_require_api_key_returns_key(monkeypatch):
    monkeypatch.delenv("SYNTHESIS_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    assert require_api_key() == "fake-key"


def test_require_api_key_exits_without_key(monkeypatch):
    monkeypatch.delenv("SYNTHESIS_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        require_api_key()


def test_require_api_key_exits_on_unsupported_provider(monkeypatch):
    monkeypatch.setenv("SYNTHESIS_LLM_PROVIDER", "anthropic")
    with pytest.raises(SystemExit):
        require_api_key()
