"""
Адаптер GDELT DOC 2.0 API — агрегатор новин, без ключа.
https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/

Query-параметри (пошуковий рядок GDELT) визначають МЕХАНІЧНЕ звуження
джерела per stream (watchlist/general/geopolitical) — сам адаптер не
вирішує, що релевантне, він лише виконує запит, що йому дали, і
нормалізує відповідь. Чи новина справді стосується активу — вирішує
analysis/news_analysis/ (DeepSeek), не тут (rule 1, data-ingestion/CLAUDE.md).

GDELT сам документує ліміт "не частіше одного запиту на 5с" (429 з
відповідним текстом) — retry-with-backoff тут той самий підхід, що й
пауза між запитами в companies/sec_edgar_adapter.py (docs/decisions.md,
2026-09-23): проактивна обробка задокументованого ліміту джерела, не
костиль на одноразову помилку.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import requests

from common.news_adapter import BaseNewsAdapter, NewsRecord, STREAMS

logger = logging.getLogger(__name__)


class GdeltError(RuntimeError):
    pass


GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# Формат часу статей у відповіді GDELT DOC API ("seendate").
_SEENDATE_FORMAT = "%Y%m%dT%H%M%SZ"

# Затримки (секунди) між повторними спробами на 429 — GDELT просить
# не частіше одного запиту на 5с, тож перша повторна спроба вже після
# паузи з запасом.
_RETRY_DELAYS = (5, 10, 20)


class GdeltAdapter(BaseNewsAdapter):
    source = "gdelt"

    def __init__(
        self,
        stream: str,
        query: str,
        session: Optional[requests.Session] = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if stream not in STREAMS:
            raise ValueError(f"Невідомий stream: {stream!r}. Доступні: {sorted(STREAMS)}")
        if not query:
            raise ValueError("query не може бути порожнім")
        self.stream = stream
        self.query = query
        self.session = session or requests.Session()
        self.sleep = sleep

    def fetch(self, maxrecords: int = 75) -> Any:
        params = {
            "query": self.query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": maxrecords,
            "sort": "datedesc",
        }

        attempts = len(_RETRY_DELAYS) + 1
        for attempt in range(attempts):
            response = self.session.get(GDELT_DOC_URL, params=params, timeout=30)
            is_last_attempt = attempt == attempts - 1

            if response.status_code == 429 and not is_last_attempt:
                delay = _RETRY_DELAYS[attempt]
                logger.warning(
                    "GDELT 429 (ліміт запитів), повтор через %ds (спроба %d/%d)",
                    delay, attempt + 1, attempts,
                )
                self.sleep(delay)
                continue

            response.raise_for_status()

            # GDELT інколи віддає 200 з порожнім/не-JSON тілом (напр.
            # занадто довгий/складний query) — той самий retry-бюджет,
            # що й для 429, а не голий JSONDecodeError користувачу.
            try:
                return response.json()
            except ValueError:
                if not is_last_attempt:
                    delay = _RETRY_DELAYS[attempt]
                    logger.warning(
                        "GDELT повернув не-JSON відповідь (перші 200 символів: %r), "
                        "повтор через %ds (спроба %d/%d)",
                        response.text[:200], delay, attempt + 1, attempts,
                    )
                    self.sleep(delay)
                    continue
                raise GdeltError(
                    f"GDELT повернув не-JSON відповідь після {attempts} спроб "
                    f"(query можливо занадто довгий/складний): {response.text[:500]!r}"
                ) from None

    def normalize(self, raw_response: Any) -> list[NewsRecord]:
        fetched_at = datetime.now(timezone.utc)
        records: list[NewsRecord] = []

        for article in raw_response.get("articles", []):
            url = article.get("url")
            title = article.get("title")
            seendate = article.get("seendate")

            if not url or not title or not seendate:
                logger.warning("Пропущено статтю без url/title/seendate: %r", article)
                continue

            try:
                published_at = datetime.strptime(seendate, _SEENDATE_FORMAT).replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                logger.warning("Не вдалось розпарсити seendate %r для %s", seendate, url)
                continue

            records.append(
                NewsRecord(
                    source=self.source,
                    external_id=url,
                    stream=self.stream,
                    title=title,
                    url=url,
                    published_at=published_at,
                    fetched_at=fetched_at,
                    raw_payload=article,
                )
            )

        return records
