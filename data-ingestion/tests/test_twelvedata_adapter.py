"""
Тести TwelveDataAdapter на збереженому прикладі відповіді (JSON,
фрагмент реальної відповіді, отриманої живим запитом користувача
2026-09-20) — жодних реальних мережевих викликів.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from quotes.twelvedata_adapter import TwelveDataAdapter

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def aapl_response():
    with open(FIXTURES_DIR / "twelvedata_aapl_response.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def adapter():
    return TwelveDataAdapter(api_key="test-key", ticker="aapl")


def test_ticker_normalized_to_uppercase(adapter):
    assert adapter.ticker == "AAPL"
    assert adapter.source == "twelvedata"


def test_missing_api_key_rejected():
    with pytest.raises(ValueError):
        TwelveDataAdapter(api_key="", ticker="AAPL")


def test_invalid_ticker_rejected():
    with pytest.raises(ValueError):
        TwelveDataAdapter(api_key="test-key", ticker="")
    with pytest.raises(ValueError):
        TwelveDataAdapter(api_key="test-key", ticker="   ")


def test_normalize_produces_close_and_volume_per_day(adapter, aapl_response):
    records = adapter.normalize(aapl_response)

    # 3 дні * 2 поля (close, volume) - 1 пропущений volume (порожній
    # рядок у 3-му запису фікстури) = 5
    assert len(records) == 5

    metric_ids = {r.metric_id for r in records}
    assert metric_ids == {"aapl_close", "aapl_volume"}

    close_records = [r for r in records if r.metric_id == "aapl_close"]
    assert len(close_records) == 3


def test_normalize_values_and_dates(adapter, aapl_response):
    records = adapter.normalize(aapl_response)
    close_18 = next(
        r for r in records if r.metric_id == "aapl_close" and r.observed_at == date(2026, 9, 18)
    )
    assert close_18.value == Decimal("336.13000")
    assert close_18.source == "twelvedata"
    assert close_18.revision is None  # revision визначає common/db.py, не адаптер

    volume_18 = next(
        r for r in records if r.metric_id == "aapl_volume" and r.observed_at == date(2026, 9, 18)
    )
    assert volume_18.value == Decimal("86433100")


def test_normalize_skips_empty_volume(adapter, aapl_response):
    records = adapter.normalize(aapl_response)
    day_16_metric_ids = {
        r.metric_id for r in records if r.observed_at == date(2026, 9, 16)
    }
    assert day_16_metric_ids == {"aapl_close"}  # volume порожній рядок цього дня


def test_normalize_raises_on_api_error_payload(adapter):
    error_response = {
        "code": 401,
        "message": "Invalid API key",
        "status": "error",
    }
    with pytest.raises(ValueError):
        adapter.normalize(error_response)


def test_normalize_raises_on_missing_values(adapter):
    with pytest.raises(ValueError):
        adapter.normalize({"meta": {}, "status": "ok"})


def test_fetch_builds_expected_params(adapter, monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"values": [], "status": "ok"}

    class FakeSession:
        def get(self, url, params=None, timeout=None):
            captured["url"] = url
            captured["params"] = params
            return FakeResponse()

    adapter.session = FakeSession()
    adapter.fetch(limit=5, observation_start="2026-01-01", observation_end="2026-08-01")

    assert captured["url"] == "https://api.twelvedata.com/time_series"
    assert captured["params"]["symbol"] == "AAPL"
    assert captured["params"]["interval"] == "1day"
    assert captured["params"]["apikey"] == "test-key"
    assert captured["params"]["outputsize"] == 5
    assert captured["params"]["start_date"] == "2026-01-01"
    assert captured["params"]["end_date"] == "2026-08-01"
