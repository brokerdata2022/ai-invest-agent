"""
Тести GdeltAdapter на збережених прикладах відповіді API — жодних
реальних мережевих викликів (див. .claude/skills/add-data-source, п.3).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from news.gdelt_adapter import GdeltAdapter, GdeltError

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def articles_response():
    with open(FIXTURES_DIR / "gdelt_articles_response.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def adapter():
    return GdeltAdapter(stream="watchlist", query='"Nvidia" OR "Federal Reserve"')


def test_unknown_stream_rejected():
    with pytest.raises(ValueError):
        GdeltAdapter(stream="not_a_real_stream", query="test")


def test_empty_query_rejected():
    with pytest.raises(ValueError):
        GdeltAdapter(stream="watchlist", query="")


def test_normalize_produces_expected_records(adapter, articles_response):
    records = adapter.normalize(articles_response)

    # Третя стаття без title, четверта з некоректним seendate — обидві пропущені.
    assert len(records) == 2

    first = records[0]
    assert first.source == "gdelt"
    assert first.stream == "watchlist"
    assert first.external_id == "https://example-news.com/articles/fed-rate-decision-2026-09-25"
    assert first.title == "Fed holds rates steady, signals caution on inflation"
    assert first.url == "https://example-news.com/articles/fed-rate-decision-2026-09-25"
    assert first.published_at == datetime(2026, 9, 25, 14, 0, 0, tzinfo=timezone.utc)
    assert first.raw_payload["domain"] == "example-news.com"


def test_normalize_skips_articles_missing_required_fields(adapter, articles_response):
    records = adapter.normalize(articles_response)
    urls = {r.url for r in records}
    assert "https://example-wire.com/no-title-here" not in urls
    assert "https://example-wire.com/bad-date" not in urls


def test_normalize_sets_fetched_at_close_to_now(adapter, articles_response):
    records = adapter.normalize(articles_response)
    now = datetime.now(timezone.utc)
    for record in records:
        assert (now - record.fetched_at).total_seconds() < 5


def test_stream_is_stored_on_every_record():
    adapter = GdeltAdapter(stream="geopolitical", query="sanctions")
    response = {
        "articles": [
            {
                "url": "https://example.com/a",
                "title": "New sanctions announced",
                "seendate": "20260925T100000Z",
            }
        ]
    }
    records = adapter.normalize(response)
    assert records[0].stream == "geopolitical"


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if self._payload is None:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._payload


class _FakeSession:
    """Повертає по одній заготовленій відповіді на кожен .get() виклик."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return self._responses.pop(0)


def test_fetch_retries_on_429_then_succeeds():
    session = _FakeSession(
        [_FakeResponse(429), _FakeResponse(429), _FakeResponse(200, {"articles": []})]
    )
    sleeps = []
    adapter = GdeltAdapter(
        stream="watchlist", query="bitcoin", session=session, sleep=sleeps.append
    )

    result = adapter.fetch()

    assert result == {"articles": []}
    assert session.calls == 3
    assert sleeps == [5, 10]  # перші дві затримки з _RETRY_DELAYS


def test_fetch_raises_after_exhausting_retries():
    # 429 на кожну спробу, включно з останньою — після вичерпання
    # retry-бюджету має піднятись помилка, не тихо повернути None.
    session = _FakeSession([_FakeResponse(429)] * 4)
    adapter = GdeltAdapter(
        stream="watchlist", query="bitcoin", session=session, sleep=lambda _: None
    )

    with pytest.raises(RuntimeError):
        adapter.fetch()


def test_fetch_retries_on_non_json_response_then_succeeds():
    # GDELT інколи віддає 200 з порожнім/не-JSON тілом (напр. занадто
    # довгий query) — той самий retry-бюджет, що й для 429.
    session = _FakeSession(
        [
            _FakeResponse(200, payload=None, text=""),
            _FakeResponse(200, {"articles": []}),
        ]
    )
    sleeps = []
    adapter = GdeltAdapter(
        stream="watchlist", query="bitcoin", session=session, sleep=sleeps.append
    )

    result = adapter.fetch()

    assert result == {"articles": []}
    assert sleeps == [5]


def test_fetch_raises_gdelt_error_after_exhausting_retries_on_non_json():
    session = _FakeSession([_FakeResponse(200, payload=None, text="")] * 4)
    adapter = GdeltAdapter(
        stream="watchlist", query="bitcoin", session=session, sleep=lambda _: None
    )

    with pytest.raises(GdeltError):
        adapter.fetch()
