"""
Тести EstatAdapter. Фікстури побудовані на підтвердженій документацією
структурі e-Stat API v3.0 (GET_STATS_DATA.STATISTICAL_DATA.CLASS_INF/
DATA_INF) — сам живий виклик до e-stat.go.jp ще НЕ підтверджений
(мережа пісочниці Claude не має туди доступу). Обов'язково звірити з
реальною відповіддю при першому запуску через Docker.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from macro.estat_adapter import EstatAdapter, METRICS, _find_class_code, _parse_estat_time

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def meta_response():
    return _load_fixture("estat_meta_response.json")


@pytest.fixture
def cpi_response():
    return _load_fixture("estat_cpi_response.json")


@pytest.fixture
def adapter():
    return EstatAdapter(api_key="test-app-id", metric_id="japan_cpi")


def test_missing_app_id_rejected():
    with pytest.raises(ValueError):
        EstatAdapter(api_key="", metric_id="japan_cpi")


def test_unknown_metric_id_rejected():
    with pytest.raises(ValueError):
        EstatAdapter(api_key="test-app-id", metric_id="not_a_real_metric")


def test_stats_data_id_resolved_from_metric_id(adapter):
    assert adapter.stats_data_id == "0004052037"
    assert adapter.source == "estat"


def test_find_class_code_exact_match(meta_response):
    class_inf = meta_response["GET_STATS_DATA"]["STATISTICAL_DATA"]["CLASS_INF"]
    assert _find_class_code(class_inf, "area", "全国") == "00000"
    assert _find_class_code(class_inf, "cat01", "総合") == "0001"


def test_find_class_code_returns_none_if_absent(meta_response):
    class_inf = meta_response["GET_STATS_DATA"]["STATISTICAL_DATA"]["CLASS_INF"]
    assert _find_class_code(class_inf, "area", "存在しない地域") is None


def test_parse_estat_time_monthly():
    assert _parse_estat_time("2026年07月") == date(2026, 7, 1)


def test_parse_estat_time_unparsable_returns_none():
    assert _parse_estat_time("не дата") is None


def test_resolve_area_and_cat01_from_meta_response(adapter, meta_response):
    mock_response = MagicMock()
    mock_response.json.return_value = meta_response
    mock_response.raise_for_status.return_value = None
    adapter.session.get = MagicMock(return_value=mock_response)

    area_code, cat01_code = adapter._resolve_area_and_cat01()
    assert area_code == "00000"
    assert cat01_code == "0001"


def test_resolve_raises_if_codes_not_found(adapter):
    broken_response = {"GET_STATS_DATA": {"STATISTICAL_DATA": {"CLASS_INF": {"CLASS_OBJ": []}}}}
    mock_response = MagicMock()
    mock_response.json.return_value = broken_response
    mock_response.raise_for_status.return_value = None
    adapter.session.get = MagicMock(return_value=mock_response)

    with pytest.raises(ValueError):
        adapter._resolve_area_and_cat01()


def test_normalize_produces_expected_records(adapter, cpi_response):
    records = adapter.normalize(cpi_response)

    # Третє значення фікстури — "-" (немає даних), має бути пропущене.
    assert len(records) == 2

    first, second = records
    assert first.observed_at == date(2026, 6, 1)
    assert first.value == Decimal("101.5")
    assert second.observed_at == date(2026, 7, 1)
    assert second.value == Decimal("101.9")
    for r in records:
        assert r.source == "estat"
        assert r.metric_id == "japan_cpi"
        assert r.revision is None


def test_normalize_applies_limit(adapter, cpi_response):
    records = adapter.normalize(cpi_response, limit=1)
    assert len(records) == 1
    assert records[0].observed_at == date(2026, 7, 1)


def test_normalize_returns_empty_on_empty_value_list(adapter):
    empty_response = {
        "GET_STATS_DATA": {
            "STATISTICAL_DATA": {
                "CLASS_INF": {"CLASS_OBJ": []},
                "DATA_INF": {"VALUE": []},
            }
        }
    }
    assert adapter.normalize(empty_response) == []


def test_all_declared_metrics_have_stats_data_id():
    for metric_id, stats_data_id in METRICS.items():
        assert isinstance(metric_id, str) and metric_id
        assert isinstance(stats_data_id, str) and stats_data_id.isdigit()
