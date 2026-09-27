"""
Тести build_prompt()/parse_response()/verify_tradable() (чисті функції
чи з підміненими залежностями, без реальної мережі/БД) — той самий
підхід, що test_synthesize_market.py.
"""

import json
from datetime import datetime, timezone

import pytest

from news_analysis.aggregate import NewsCluster
import news_analysis.discover_candidates as discover_candidates
from news_analysis.discover_candidates import (
    CandidateResponseError,
    build_prompt,
    call_llm,
    parse_response,
    verify_tradable,
)

CLUSTER = NewsCluster(
    representative_title="Acme Robotics unveils breakthrough humanoid robot line",
    source_count=6,
    asset_ids=[],
    dominant_direction="up",
    direction_counts={"up": 5, "down": 0, "neutral": 1, "unclear": 0},
    summaries=["Acme Robotics announced a new humanoid robot line with major retail partners."],
    urls=["https://example.com/a"],
    earliest_published_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
    latest_published_at=datetime(2026, 9, 26, tzinfo=timezone.utc),
)

VALID_RESPONSE = {
    "candidates": [
        {"ticker": "ACME", "company_name": "Acme Robotics Inc.", "reasoning": "New humanoid robot line with retail partners."},
    ]
}

EMPTY_RESPONSE = {"candidates": []}


def test_build_prompt_includes_clusters_and_already_tracked():
    prompt = build_prompt([CLUSTER], ["AAPL", "NVDA"])
    assert "AAPL" in prompt
    assert "NVDA" in prompt
    assert "Acme Robotics unveils breakthrough humanoid robot line" in prompt
    assert "6 джерел" in prompt


def test_parse_response_valid():
    candidates = parse_response(json.dumps(VALID_RESPONSE))
    assert len(candidates) == 1
    assert candidates[0]["ticker"] == "ACME"


def test_parse_response_empty_list_is_valid():
    assert parse_response(json.dumps(EMPTY_RESPONSE)) == []


def test_parse_response_rejects_invalid_json():
    with pytest.raises(CandidateResponseError):
        parse_response("not json")


def test_parse_response_rejects_missing_candidates_field():
    with pytest.raises(CandidateResponseError):
        parse_response(json.dumps({}))


def test_parse_response_rejects_non_list_candidates():
    with pytest.raises(CandidateResponseError):
        parse_response(json.dumps({"candidates": "ACME"}))


def test_parse_response_rejects_candidate_missing_fields():
    data = {"candidates": [{"ticker": "ACME", "company_name": "Acme Robotics Inc."}]}
    with pytest.raises(CandidateResponseError):
        parse_response(json.dumps(data))


def test_call_llm_rejects_unsupported_provider(monkeypatch):
    monkeypatch.setattr(discover_candidates, "LLM_PROVIDER", "anthropic")
    with pytest.raises(ValueError):
        call_llm("prompt", "system", api_key="fake-key")


def test_verify_tradable_returns_none_when_adapter_rejects_ticker(monkeypatch):
    class FakeAdapter:
        def __init__(self, api_key, ticker):
            pass

        def collect(self, limit):
            raise ValueError("symbol not found")

    monkeypatch.setattr(discover_candidates, "TwelveDataAdapter", FakeAdapter)

    result = verify_tradable(conn=None, ticker="FAKE", twelvedata_api_key="key")
    assert result is None


def test_verify_tradable_returns_none_when_no_records(monkeypatch):
    class FakeAdapter:
        def __init__(self, api_key, ticker):
            pass

        def collect(self, limit):
            return []

    monkeypatch.setattr(discover_candidates, "TwelveDataAdapter", FakeAdapter)

    result = verify_tradable(conn=None, ticker="EMPTY", twelvedata_api_key="key")
    assert result is None


def test_verify_tradable_confirms_when_price_change_found(monkeypatch):
    class FakeRecord:
        pass

    class FakeAdapter:
        def __init__(self, api_key, ticker):
            pass

        def collect(self, limit):
            return [FakeRecord()]

    monkeypatch.setattr(discover_candidates, "TwelveDataAdapter", FakeAdapter)
    monkeypatch.setattr(discover_candidates, "insert_observations", lambda conn, records: None)
    monkeypatch.setattr(discover_candidates, "fetch_price_change", lambda conn, ticker, days: "a-price-change")

    result = verify_tradable(conn=None, ticker="ACME", twelvedata_api_key="key")
    assert result == "a-price-change"
