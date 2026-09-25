from news.queries import WATCHLIST_TERMS, build_watchlist_query


def test_build_watchlist_query_includes_every_asset_term():
    query = build_watchlist_query()
    for term in WATCHLIST_TERMS.values():
        assert term in query


def test_build_watchlist_query_is_a_single_or_group():
    query = build_watchlist_query()
    assert query.startswith("(")
    assert query.endswith(")")
    assert " OR " in query
