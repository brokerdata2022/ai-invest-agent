from news_analysis.run_news_analysis import resolve_tracked_assets

# Фікстура, що раніше йшла статично з news/queries.py:WATCHLIST_ASSET_IDS
# (2026-10-03: тепер main() рахує це живим викликом
# common/watchlist_db.py:fetch_asset_ids(conn) і передає явно).
_DEFAULTS = {"watchlist": ["btc", "xauusd"]}


def test_explicit_overrides_default():
    result = resolve_tracked_assets("watchlist", ["AAPL", "NVDA"], default_tracked_assets=_DEFAULTS)
    assert result == ["AAPL", "NVDA"]


def test_watchlist_falls_back_to_default_tracked_assets():
    result = resolve_tracked_assets("watchlist", None, default_tracked_assets=_DEFAULTS)
    assert result is not None
    assert "btc" in result
    assert "xauusd" in result


def test_general_has_no_default():
    assert resolve_tracked_assets("general", None, default_tracked_assets=_DEFAULTS) is None


def test_geopolitical_has_no_default():
    assert resolve_tracked_assets("geopolitical", None, default_tracked_assets=_DEFAULTS) is None


def test_no_default_tracked_assets_given_returns_none():
    # default_tracked_assets не передано взагалі (None) — той самий
    # ефект, що порожній словник, не падає.
    assert resolve_tracked_assets("watchlist", None) is None


def test_watchlist_includes_screening_tickers_when_provided():
    result = resolve_tracked_assets(
        "watchlist", None, screening_tickers=["AAPL", "NVDA"], default_tracked_assets=_DEFAULTS
    )
    assert "AAPL" in result
    assert "NVDA" in result
    assert "btc" in result  # дефолтний watchlist усе одно на місці


def test_watchlist_without_screening_tickers_unchanged():
    result = resolve_tracked_assets(
        "watchlist", None, screening_tickers=None, default_tracked_assets=_DEFAULTS
    )
    assert "AAPL" not in result
    assert "btc" in result


def test_screening_tickers_ignored_when_stream_has_no_default():
    result = resolve_tracked_assets(
        "general", None, screening_tickers=["AAPL"], default_tracked_assets=_DEFAULTS
    )
    assert result is None


def test_explicit_overrides_even_with_screening_tickers():
    result = resolve_tracked_assets(
        "watchlist", ["AAPL"], screening_tickers=["NVDA"], default_tracked_assets=_DEFAULTS
    )
    assert result == ["AAPL"]
