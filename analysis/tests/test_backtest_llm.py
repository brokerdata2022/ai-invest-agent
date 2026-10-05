"""
Тести backtest_llm_metric()/format_verdict() — forecast_fn
інжектується (фейкова функція замість LLM), тож мережі/БД не потрібно.
Той самий підхід, що test_backtest.py для лінійної моделі.
"""

from forecasting.backtest_llm import (
    backtest_llm_metric,
    format_verdict,
    resolve_backtest_route,
)
from llm_common import resolve_route

# fetch_recent() віддає НАЙНОВІШЕ ПЕРШЕ — саме в такому порядку
# backtest_llm_metric() очікує вхід.
OBSERVATIONS_DESC = [
    {"observed_at": "2026-08-31", "value": 110.0},
    {"observed_at": "2026-07-31", "value": 108.0},
    {"observed_at": "2026-06-30", "value": 106.0},
    {"observed_at": "2026-05-31", "value": 104.0},
    {"observed_at": "2026-04-30", "value": 102.0},
    {"observed_at": "2026-03-31", "value": 100.0},
]


def _perfect_forecast(history_rows):
    """Знає справжній крок серії (+2) — ідеальний прогноз."""
    return float(history_rows[-1]["value"]) + 2.0


def test_backtest_checks_only_requested_number_of_points():
    result = backtest_llm_metric(
        "cpi", OBSERVATIONS_DESC, _perfect_forecast, points=2, min_history=3
    )
    assert result["n_points"] == 2
    assert result["n_skipped"] == 0


def test_backtest_respects_min_history_floor():
    """points=99 не може опуститись нижче min_history — інакше перші
    точки прогнозувались би з порожньої історії."""
    result = backtest_llm_metric(
        "cpi", OBSERVATIONS_DESC, _perfect_forecast, points=99, min_history=4
    )
    assert result["n_points"] == len(OBSERVATIONS_DESC) - 4


def test_backtest_perfect_forecast_beats_naive():
    result = backtest_llm_metric(
        "cpi", OBSERVATIONS_DESC, _perfect_forecast, points=3, min_history=3
    )
    assert result["llm_mae"] == 0.0
    assert result["naive_mae"] > 0
    assert "LLM точніший" in format_verdict(result)


def test_backtest_forecast_fn_never_sees_the_future():
    """Честний out-of-sample: у кожному виклику історія обривається
    ДО точки, що перевіряється."""
    seen = []

    def spy(history_rows):
        seen.append([r["observed_at"] for r in history_rows])
        return float(history_rows[-1]["value"])

    backtest_llm_metric("cpi", OBSERVATIONS_DESC, spy, points=2, min_history=4)

    chronological_dates = [o["observed_at"] for o in OBSERVATIONS_DESC[::-1]]
    assert seen == [chronological_dates[:4], chronological_dates[:5]]


def test_backtest_skipped_points_are_counted_not_hidden():
    """None-прогноз (збійна відповідь LLM) не рахується як влучення —
    точка пропускається й це видно в n_skipped."""
    calls = {"n": 0}

    def flaky(history_rows):
        calls["n"] += 1
        return None if calls["n"] == 1 else float(history_rows[-1]["value"]) + 2.0

    result = backtest_llm_metric(
        "cpi", OBSERVATIONS_DESC, flaky, points=2, min_history=4
    )
    assert result["n_points"] == 1
    assert result["n_skipped"] == 1
    assert result["llm_mae"] == 0.0


def test_backtest_baselines_exclude_points_llm_skipped():
    """Пропущена точка виходить і з базових ліній — інакше MAE
    порівнювались би на РІЗНИХ наборах точок (живий кейс
    `unemployment_rate` 2026-10-04: naive отримував безкоштовну точку з
    похибкою 0, і вердикт перевертався)."""
    result = backtest_llm_metric(
        "cpi", OBSERVATIONS_DESC, lambda rows: None, points=2, min_history=4
    )
    assert result["n_points"] == 0
    assert result["n_skipped"] == 2
    assert result["llm_mae"] is None
    assert result["naive_mae"] is None
    assert result["trend_mae"] is None


def test_backtest_all_three_maes_measured_on_equal_point_counts():
    """Головна гарантія честності порівняння: скільки точок у LLM —
    стільки ж у кожної базової лінії."""
    calls = {"n": 0}

    def flaky(history_rows):
        calls["n"] += 1
        return None if calls["n"] == 1 else float(history_rows[-1]["value"]) + 2.0

    result = backtest_llm_metric(
        "cpi", OBSERVATIONS_DESC, flaky, points=3, min_history=3
    )
    # 3 точки запрошено, 1 пропущено → 2 в кожній з трьох моделей.
    assert result["n_points"] == 2
    assert result["n_skipped"] == 1
    assert result["llm_mae"] is not None
    assert result["naive_mae"] == 2.0  # рівний крок +2 на обох точках
    assert result["trend_mae"] is not None


def test_format_verdict_without_points():
    verdict = format_verdict(
        {"llm_mae": None, "naive_mae": 1.0, "trend_mae": None, "n_points": 0}
    )
    assert "вердикту немає" in verdict


def test_format_verdict_naive_wins():
    verdict = format_verdict(
        {"llm_mae": 2.0, "naive_mae": 1.0, "trend_mae": None, "n_points": 3}
    )
    assert "naive кращий" in verdict
    assert "100.0%" in verdict


def test_format_verdict_exact_tie_reads_as_tie():
    """Живий кейс `unemployment_rate` (2026-10-04): MAE рівно однакові,
    а вивід казав "naive кращий — LLM гірший на 0.0%"."""
    verdict = format_verdict(
        {"llm_mae": 0.0625, "naive_mae": 0.0625, "trend_mae": 0.1263, "n_points": 8}
    )
    assert "нічия" in verdict
    assert "гірший" not in verdict


def test_format_verdict_handles_flawless_naive():
    """Плоска серія: naive MAE = 0, відносна різниця не визначена —
    ділення на нуль замість вердикту було б падінням."""
    verdict = format_verdict(
        {"llm_mae": 0.5, "naive_mae": 0.0, "trend_mae": None, "n_points": 4}
    )
    assert "безпомилковий" in verdict


# ============================================================
# Перекриття маршруту з CLI
# ============================================================
# Додано 2026-10-05: бектест за визначенням міряє РІЗНІ моделі на тих
# самих точках (живий кейс — порівняти Opus 5 і Sonnet 5), а правити
# для цього config.py означало б заодно перемкнути бойовий прогноз.


class _Args:
    def __init__(self, provider=None, model=None, effort=None):
        self.provider = provider
        self.model = model
        self.effort = effort


def test_route_comes_from_config_without_flags(monkeypatch):
    monkeypatch.delenv("SYNTHESIS_LLM_PROVIDER", raising=False)
    route = resolve_backtest_route(_Args())
    assert route == resolve_route("metric_forecast_backtest")


def test_model_flag_overrides_only_the_model(monkeypatch):
    monkeypatch.delenv("SYNTHESIS_LLM_PROVIDER", raising=False)
    configured = resolve_route("metric_forecast_backtest")

    route = resolve_backtest_route(_Args(model="claude-sonnet-5"))

    assert route.model == "claude-sonnet-5"
    assert route.provider == configured.provider
    # effort не чіпається — інакше порівняння моделей змінювало б
    # ДВІ змінні одночасно й нічого не доводило.
    assert route.effort == configured.effort


def test_provider_and_effort_flags_apply(monkeypatch):
    monkeypatch.delenv("SYNTHESIS_LLM_PROVIDER", raising=False)
    route = resolve_backtest_route(_Args(provider="deepseek", model="deepseek-chat", effort=None))
    assert (route.provider, route.model) == ("deepseek", "deepseek-chat")

    route = resolve_backtest_route(_Args(effort="low"))
    assert route.effort == "low"
