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
