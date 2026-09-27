"""
Тести update_forecasts_cycle() з підміненими БД-функціями
(get_detected_entries/run_forecast) — той самий підхід, що
test_compare_releases.py (monkeypatch, без реальної БД).
"""

from forecasting.update_forecasts import update_forecasts_cycle

CPI_ENTRY = {"id": 1, "source": "fred", "metric_id": "cpi", "expected_value": "0.4%"}


def test_update_forecasts_cycle_runs_forecast_for_forecastable_metric(monkeypatch):
    called = []

    monkeypatch.setattr(
        "forecasting.update_forecasts.get_detected_entries",
        lambda conn: [CPI_ENTRY],
    )
    monkeypatch.setattr(
        "forecasting.update_forecasts.run_forecast",
        lambda conn, metric_id: called.append(metric_id) or 42,
    )

    updated = update_forecasts_cycle(conn=None)

    assert updated == ["cpi"]
    assert called == ["cpi"]


def test_update_forecasts_cycle_skips_metrics_without_forecast_method(monkeypatch):
    other_entry = dict(CPI_ENTRY, id=2, metric_id="unemployment_rate")
    called = []

    monkeypatch.setattr(
        "forecasting.update_forecasts.get_detected_entries",
        lambda conn: [other_entry],
    )
    monkeypatch.setattr(
        "forecasting.update_forecasts.run_forecast",
        lambda conn, metric_id: called.append(metric_id) or 1,
    )

    updated = update_forecasts_cycle(conn=None)

    assert updated == []
    assert called == []


def test_update_forecasts_cycle_continues_after_one_metric_fails(monkeypatch):
    calls = []

    class FakeConn:
        def rollback(self):
            calls.append("rollback")

    def fake_get_detected(conn):
        return [CPI_ENTRY]

    def fake_run_forecast(conn, metric_id):
        calls.append(metric_id)
        raise RuntimeError("boom")

    monkeypatch.setattr("forecasting.update_forecasts.get_detected_entries", fake_get_detected)
    monkeypatch.setattr("forecasting.update_forecasts.run_forecast", fake_run_forecast)

    updated = update_forecasts_cycle(conn=FakeConn())

    assert updated == []
    assert calls == ["cpi", "rollback"]
