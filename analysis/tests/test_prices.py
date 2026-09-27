from decimal import Decimal

from news_analysis.prices import ASSET_PRICE_SOURCES, _resolve_price_source, compute_pct_change


def test_compute_pct_change_positive():
    change = compute_pct_change(
        "xauusd", Decimal("4000"), "2026-09-20", Decimal("4200"), "2026-09-26"
    )
    assert change.pct_change == Decimal("5")
    assert change.asset_id == "xauusd"


def test_compute_pct_change_negative():
    change = compute_pct_change(
        "wti_crude", Decimal("100"), "2026-09-20", Decimal("92"), "2026-09-26"
    )
    assert change.pct_change == Decimal("-8")


def test_compute_pct_change_zero_start_value_does_not_divide_by_zero():
    change = compute_pct_change("eurusd", Decimal("0"), "2026-09-20", Decimal("1"), "2026-09-26")
    assert change.pct_change == Decimal("0")


def test_compute_pct_change_no_movement():
    change = compute_pct_change(
        "brent_crude", Decimal("80"), "2026-09-20", Decimal("80"), "2026-09-26"
    )
    assert change.pct_change == Decimal("0")


def test_asset_price_sources_known_watchlist_assets():
    # usdjpy_fx_rate -- свідома невідповідність з asset_id "usdjpy",
    # замаплена тут явно (docs/decisions.md, 2026-09-26).
    assert ASSET_PRICE_SOURCES["usdjpy"] == ("fred", "usdjpy_fx_rate")
    assert ASSET_PRICE_SOURCES["xauusd"] == ("twelvedata", "xauusd_close")
    assert "xagusd" not in ASSET_PRICE_SOURCES  # заблоковано тарифом, свідомо відсутнє


def test_resolve_price_source_uses_explicit_mapping_when_known():
    assert _resolve_price_source("usdjpy") == ("fred", "usdjpy_fx_rate")


def test_resolve_price_source_falls_back_to_twelvedata_convention_for_ticker():
    # тикер зі скринінгу (docs/news-purpose.md, "Ціль 2") -- не в
    # ASSET_PRICE_SOURCES, здогад за конвенцією twelvedata_adapter.py.
    assert _resolve_price_source("AAPL") == ("twelvedata", "aapl_close")


def test_resolve_price_source_fallback_lowercases_ticker():
    assert _resolve_price_source("NVDA") == ("twelvedata", "nvda_close")
