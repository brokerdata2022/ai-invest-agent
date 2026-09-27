"""
Тест реєстру RSS_FEEDS — чиста перевірка конфігурації, без мережі
(сам RssAdapter уже тестується на фікстурах у test_rss_adapter.py).
"""

from news.rss_feeds import RSS_FEEDS

_EXPECTED_FEEDS = {
    "fed_rss", "ecb_rss", "boj_rss",
    "bbc_rss", "aljazeera_rss", "guardian_rss", "npr_rss", "skynews_rss", "dw_rss",
}


def test_all_expected_feeds_registered():
    assert set(RSS_FEEDS) == _EXPECTED_FEEDS


def test_every_feed_has_https_url():
    for name, cfg in RSS_FEEDS.items():
        assert cfg["url"].startswith("https://"), f"{name}: url має бути https"


def test_every_feed_is_geopolitical_stream():
    # Усі RSS-фіди (центробанки й широкі редакційні стрічки) пишуться
    # в geopolitical — макро-політичний контекст без прив'язки до
    # конкретного watchlist-активу (docs/decisions.md, 2026-09-27).
    for name, cfg in RSS_FEEDS.items():
        assert cfg["stream"] == "geopolitical", f"{name}: неочікуваний stream {cfg['stream']!r}"
