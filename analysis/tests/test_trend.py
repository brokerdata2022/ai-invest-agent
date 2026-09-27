"""
Тести trend.py — чисті функції, відомі числові приклади (без БД/мережі).
"""

from forecasting.trend import linear_trend_forecast, naive_forecast


def test_naive_forecast_returns_last_value():
    assert naive_forecast([1.0, 2.0, 3.0]) == 3.0


def test_naive_forecast_empty_returns_none():
    assert naive_forecast([]) is None


def test_linear_trend_forecast_perfect_line():
    # y = x -> наступна точка (x=4) має дати 4.0
    assert linear_trend_forecast([0.0, 1.0, 2.0, 3.0]) == 4.0


def test_linear_trend_forecast_extrapolates_multiple_periods():
    assert linear_trend_forecast([0.0, 1.0, 2.0, 3.0], periods_ahead=3) == 6.0


def test_linear_trend_forecast_constant_series():
    # без тренду -> прогноз = те саме значення
    assert linear_trend_forecast([5.0, 5.0, 5.0]) == 5.0


def test_linear_trend_forecast_needs_at_least_two_points():
    assert linear_trend_forecast([1.0]) is None
    assert linear_trend_forecast([]) is None
