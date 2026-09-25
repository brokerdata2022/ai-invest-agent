"""
Адаптер офіційних RSS-фідів (центробанки, статслужби) — first-party
джерело, надійніше за GDELT, але вужче за обсягом (тільки те, що
джерело саме публікує як прес-реліз, не весь ринковий контекст).

RSS 2.0 <item>: title/link/pubDate — обов'язкові (без них запис не
нормалізується). description — опційно, не всі фіди його дають
(перевірено живо 2026-09-26: Fed дає, ECB — ні) — якщо є, йде в
raw_payload для аудиту (rule 6), окремого поля під нього в NewsRecord
нема (той самий набір полів, що й у GDELT-адаптера).

На відміну від GdeltAdapter, source — параметр конструктора, не
фіксований клас-атрибут: кожен RSS-фід (fed_rss/ecb_rss/...) — окреме
джерело (news/rss_feeds.py), той самий підхід, що й один клас
адаптера на кілька series/тикерів в інших модулях data-ingestion/.
"""

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional
from xml.etree import ElementTree

import requests

from common.news_adapter import BaseNewsAdapter, NewsRecord, STREAMS

logger = logging.getLogger(__name__)


class RssAdapter(BaseNewsAdapter):
    def __init__(
        self,
        source: str,
        stream: str,
        feed_url: str,
        session: Optional[requests.Session] = None,
    ):
        if stream not in STREAMS:
            raise ValueError(f"Невідомий stream: {stream!r}. Доступні: {sorted(STREAMS)}")
        if not feed_url:
            raise ValueError("feed_url не може бути порожнім")
        self.source = source
        self.stream = stream
        self.feed_url = feed_url
        self.session = session or requests.Session()

    def fetch(self) -> Any:
        response = self.session.get(self.feed_url, timeout=30)
        response.raise_for_status()
        # Сирі байти, НЕ .text: живий запит до Fed (2026-09-26) показав
        # HTTP-заголовок без charset при UTF-8 BOM у тілі — requests за
        # RFC-дефолтом вгадує ISO-8859-1 для .text, BOM перетворюється
        # на сміттєві символи перед "<?xml...", XML стає невалідним.
        # ElementTree сам коректно розпізнає кодування й BOM з байтів.
        return response.content

    def normalize(self, raw_response: Any) -> list[NewsRecord]:
        fetched_at = datetime.now(timezone.utc)
        records: list[NewsRecord] = []

        try:
            root = ElementTree.fromstring(raw_response)
        except ElementTree.ParseError:
            logger.warning("Не вдалось розпарсити RSS з %s (%s) — невалідний XML", self.feed_url, self.source)
            return []

        for item in root.iter("item"):
            title = _child_text(item, "title")
            link = _child_text(item, "link")
            pub_date_raw = _child_text(item, "pubDate")

            if not title or not link or not pub_date_raw:
                logger.warning(
                    "Пропущено item без title/link/pubDate (%s): title=%r link=%r pubDate=%r",
                    self.source, title, link, pub_date_raw,
                )
                continue

            try:
                published_at = parsedate_to_datetime(pub_date_raw)
            except (TypeError, ValueError):
                logger.warning("Не вдалось розпарсити pubDate %r для %s (%s)", pub_date_raw, link, self.source)
                continue
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)

            records.append(
                NewsRecord(
                    source=self.source,
                    external_id=link,
                    stream=self.stream,
                    title=title,
                    url=link,
                    published_at=published_at,
                    fetched_at=fetched_at,
                    raw_payload={
                        "title": title,
                        "link": link,
                        "pubDate": pub_date_raw,
                        "description": _child_text(item, "description"),
                    },
                )
            )

        return records


def _child_text(item: ElementTree.Element, tag: str) -> Optional[str]:
    el = item.find(tag)
    if el is None or el.text is None:
        return None
    return el.text.strip()
