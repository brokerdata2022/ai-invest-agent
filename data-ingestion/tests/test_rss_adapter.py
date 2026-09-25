"""
Тести RssAdapter на збережених прикладах відповіді (реальна структура
Fed/ECB RSS, перевірена живими запитами 2026-09-26) — жодних реальних
мережевих викликів (див. .claude/skills/add-data-source, п.3).
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from news.rss_adapter import RssAdapter

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


@pytest.fixture
def fed_response():
    return _fixture("fed_rss_response.xml")


@pytest.fixture
def ecb_response():
    return _fixture("ecb_rss_response.xml")


@pytest.fixture
def fed_adapter():
    return RssAdapter(
        source="fed_rss",
        stream="geopolitical",
        feed_url="https://www.federalreserve.gov/feeds/press_all.xml",
    )


@pytest.fixture
def ecb_adapter():
    return RssAdapter(
        source="ecb_rss",
        stream="geopolitical",
        feed_url="https://www.ecb.europa.eu/rss/press.xml",
    )


def test_unknown_stream_rejected():
    with pytest.raises(ValueError):
        RssAdapter(source="fed_rss", stream="not_a_real_stream", feed_url="https://example.com/rss")


def test_empty_feed_url_rejected():
    with pytest.raises(ValueError):
        RssAdapter(source="fed_rss", stream="geopolitical", feed_url="")


def test_normalize_fed_produces_expected_records(fed_adapter, fed_response):
    records = fed_adapter.normalize(fed_response)

    # Третій item без pubDate -- має бути пропущений.
    assert len(records) == 2

    first = records[0]
    assert first.source == "fed_rss"
    assert first.stream == "geopolitical"
    assert first.title == "Federal Reserve Board announces approval of application by Peoples Bancorp Inc."
    assert first.url == "https://www.federalreserve.gov/newsevents/pressreleases/orders20260925a.htm"
    assert first.external_id == first.url
    assert first.published_at == datetime(2026, 9, 25, 20, 30, 0, tzinfo=timezone.utc)
    assert first.raw_payload["description"] == (
        "Federal Reserve Board announces approval of application by Peoples Bancorp Inc."
    )


def test_normalize_skips_item_missing_pubdate(fed_adapter, fed_response):
    records = fed_adapter.normalize(fed_response)
    urls = {r.url for r in records}
    assert "https://www.federalreserve.gov/newsevents/pressreleases/broken.htm" not in urls


def test_normalize_ecb_handles_missing_description(ecb_adapter, ecb_response):
    # ECB-фід не дає <description> взагалі -- має нормалізуватись без
    # падіння, з description=None у raw_payload.
    records = ecb_adapter.normalize(ecb_response)
    assert len(records) == 2
    assert records[0].raw_payload["description"] is None


def test_normalize_ecb_parses_offset_pubdate(ecb_adapter, ecb_response):
    records = ecb_adapter.normalize(ecb_response)
    # +0200 -- не GMT/UTC як у Fed, той самий парсер має впоратись.
    assert records[0].published_at == datetime(
        2026, 9, 24, 14, 0, 0, tzinfo=timezone(timedelta(hours=2))
    )


def test_normalize_sets_fetched_at_close_to_now(fed_adapter, fed_response):
    records = fed_adapter.normalize(fed_response)
    now = datetime.now(timezone.utc)
    for record in records:
        assert (now - record.fetched_at).total_seconds() < 5


def test_normalize_handles_malformed_xml_without_raising(fed_adapter):
    records = fed_adapter.normalize("<rss><channel><item><title>broken")
    assert records == []


def test_normalize_handles_empty_channel(fed_adapter):
    records = fed_adapter.normalize("<rss><channel></channel></rss>")
    assert records == []


def test_normalize_handles_utf8_bom_bytes(fed_adapter, fed_response):
    # Regression: живий запит до Fed (2026-09-26) повернув UTF-8 BOM
    # без charset у HTTP-заголовку -- .text помилково вгадував
    # ISO-8859-1 і ламав XML. fetch() тепер повертає response.content
    # (байти) саме з цієї причини -- цей тест підтверджує, що
    # normalize() коректно парсить байти з BOM (не .text/str).
    raw_bytes_with_bom = b"\xef\xbb\xbf" + fed_response.encode("utf-8")
    records = fed_adapter.normalize(raw_bytes_with_bom)
    assert len(records) == 2
    assert records[0].title == "Federal Reserve Board announces approval of application by Peoples Bancorp Inc."
