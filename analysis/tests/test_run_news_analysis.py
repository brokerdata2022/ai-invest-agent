from news_analysis.run_news_analysis import resolve_tracked_assets


def test_explicit_overrides_default():
    result = resolve_tracked_assets("watchlist", ["AAPL", "NVDA"])
    assert result == ["AAPL", "NVDA"]


def test_watchlist_falls_back_to_watchlist_asset_ids():
    result = resolve_tracked_assets("watchlist", None)
    assert result is not None
    assert "btc" in result
    assert "xauusd" in result


def test_general_has_no_default():
    assert resolve_tracked_assets("general", None) is None


def test_geopolitical_has_no_default():
    assert resolve_tracked_assets("geopolitical", None) is None


def test_watchlist_includes_screening_tickers_when_provided():
    result = resolve_tracked_assets("watchlist", None, screening_tickers=["AAPL", "NVDA"])
    assert "AAPL" in result
    assert "NVDA" in result
    assert "btc" in result  # фіксований WATCHLIST_ASSET_IDS усе одно на місці


def test_watchlist_without_screening_tickers_unchanged():
    result = resolve_tracked_assets("watchlist", None, screening_tickers=None)
    assert "AAPL" not in result
    assert "btc" in result


def test_screening_tickers_ignored_when_stream_has_no_default():
    assert resolve_tracked_assets("general", None, screening_tickers=["AAPL"]) is None


def test_explicit_overrides_even_with_screening_tickers():
    result = resolve_tracked_assets("watchlist", ["AAPL"], screening_tickers=["NVDA"])
    assert result == ["AAPL"]
