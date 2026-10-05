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

timespan (за замовчуванням "1d" — 24г, 2026-09-28 рішення користувача: збирати лише свіжі статті, докладніше common/news_db.py) обмежує пошук останніми N днями —
без нього GDELT віддає найновіші `maxrecords` збігів БЕЗ ОБМЕЖЕННЯ
глибини в часі: для вузьких query це означає статті кількамісячної
давнини (живо виявлено 2026-09-26 — стаття про ставку з липня була в
результатах у вересні, коли рішення вже давно прийняте/застаріле) —
для мети "розуміти ПОТОЧНИЙ напрямок ринку" (docs/decisions.md,
2026-09-25) стара стаття не просто марна, а шкідлива, якщо DeepSeek
проаналізує її як актуальний сигнал.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import requests

from common.news_adapter import BaseNewsAdapter, NewsRecord, STREAMS
from config import GDELT_RETRY_DELAYS

logger = logging.getLogger(__name__)


class GdeltError(RuntimeError):
    pass


GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# Формат часу статей у відповіді GDELT DOC API ("seendate").
_SEENDATE_FORMAT = "%Y%m%dT%H%M%SZ"

# Затримки (секунди) між повторними спробами на 429 — GDELT просить
# не частіше одного запиту на 5с, тож перша повторна спроба вже після
# паузи з запасом.
# Затримки повторів і глобальний ліміт — `config.py` розділ 8 (єдиний
# конфіг на весь агент). Було локальне (5, 10, 20) — docs/decisions.md
# 2026-10-05: швидкий повтор на 429 лише глибше заганяв IP у штрафний
# стан GDELT.
_RETRY_DELAYS = tuple(GDELT_RETRY_DELAYS)


def validate_gdelt_term(term: str, session: Optional[requests.Session] = None) -> bool:
    """ОДИН (без retry) легкий GDELT-запит лише з цим ОДНИМ квотованим
    терміном — True, якщо GDELT прийняв його (валідний JSON), False
    якщо відхилив (напр. "The specified phrase is too short" — той
    самий "Uber"-урок, docs/decisions.md 2026-09-25: дуже короткі/
    загальновживані слова GDELT відхиляє навіть у лапках) чи мережева
    помилка. Без retry навмисно — ЦЯ відмова детермінована (та сама
    фраза не стане "достатньо довгою" від повторної спроби), на
    відміну від транзієнтного 429, retry тут лише видовжив би
    очікування даремно.

    Додано 2026-10-04 (orchestration/telegram_commands.py:
    /watchlist_add, docs/decisions.md) — живий кейс: доданий без цієї
    перевірки термін '"BNB"' зламав ЦІЛИЙ watchlist GDELT-запит (один
    поганий OR-термін псує запит для ВСІХ активів одразу, не лише
    нового) — валідація тут запобігає цьому ДО того, як термін
    потрапить у продакшн-запит."""
    session = session or requests.Session()
    try:
        response = session.get(
            GDELT_DOC_URL,
            params={
                "query": f'"{term}"', "mode": "artlist", "format": "json",
                "maxrecords": 1, "timespan": "1d",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.exceptions.RequestException, ValueError):
        return False

    # Мʼякий троттл (200 з тілом `{}`, без ключа "articles") — GDELT
    # НЕ оцінював термін, тож "валідний" сказати не можна. Повертаємо
    # False СВІДОМО, хоч це й не "термін поганий": ціна помилки
    # асиметрична. Хибне True пускає неперевірений термін у СПІЛЬНИЙ
    # watchlist-запит, і один поганий OR-терм ламає новини для ВСІХ
    # активів одразу (живий кейс "BNB", 2026-10-04); хибне False лише
    # додає актив без новинного терміна — градація мʼяка й зворотна
    # (common/watchlist_db.py:set_search_term). У лозі причина
    # названа окремо, щоб "не змогли перевірити" не читалось як
    # "GDELT відхилив" (2026-10-05, docs/decisions.md).
    if "articles" not in payload:
        logger.warning(
            "Не вдалось перевірити термін %r: GDELT віддав 200 без 'articles' "
            "(мʼякий троттл ліміту запитів). Термін НЕ додається в спільний "
            "запит — повторіть пізніше.",
            term,
        )
        return False

    return True


class GdeltAdapter(BaseNewsAdapter):
    source = "gdelt"

    def __init__(
        self,
        stream: str,
        query: str,
        session: Optional[requests.Session] = None,
        sleep: Callable[[float], None] = time.sleep,
        pacer: Optional[Callable[[], None]] = None,
    ):
        if stream not in STREAMS:
            raise ValueError(f"Невідомий stream: {stream!r}. Доступні: {sorted(STREAMS)}")
        if not query:
            raise ValueError("query не може бути порожнім")
        self.stream = stream
        self.query = query
        self.session = session or requests.Session()
        self.sleep = sleep
        # Глобальний (міжпроцесний) обмежувач швидкості — викликається
        # ПЕРЕД КОЖНИМ запитом, включно з повторами після 429
        # (`common/rate_limit.py:make_pacer`). None = без обмеження:
        # так лишається для тестів і для одноразового ручного запуску,
        # але джоби ОБОВʼЯЗКОВО передають pacer — без нього три
        # процеси збору знову перевищать ліміт GDELT (docs/decisions.md,
        # 2026-10-05).
        self.pacer = pacer

    def fetch(self, maxrecords: int = 75, timespan: str = "1d") -> Any:
        params = {
            "query": self.query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": maxrecords,
            "sort": "datedesc",
            "timespan": timespan,
        }

        attempts = len(_RETRY_DELAYS) + 1
        for attempt in range(attempts):
            if self.pacer is not None:
                self.pacer()
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
                payload = response.json()
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

            # МʼЯКИЙ ТРОТТЛ GDELT: HTTP 200 з тілом `{}` — відповідь БЕЗ
            # ключа "articles" взагалі. Живо виявлено 2026-10-05
            # (docs/decisions.md): саме через це потоки `general`/
            # `watchlist` тижнями писали в лог "Отримано 0 статей",
            # скрипт виходив з кодом 0, а runner.py вважав прогін
            # УСПІШНИМ — тихе втрачання даних без жодного сигналу.
            #
            # Різниця, на якій тримається розрізнення: справжнє "немає
            # збігів" приходить як {"articles": []} — ключ Є, список
            # порожній. Відсутність самого ключа означає, що GDELT
            # відмовив у обслуговуванні, тож це той самий шлях, що 429.
            if "articles" not in payload:
                if not is_last_attempt:
                    delay = _RETRY_DELAYS[attempt]
                    logger.warning(
                        "GDELT віддав 200 без ключа 'articles' (мʼякий троттл, "
                        "тіло: %r), повтор через %ds (спроба %d/%d)",
                        response.text[:200], delay, attempt + 1, attempts,
                    )
                    self.sleep(delay)
                    continue
                raise GdeltError(
                    f"GDELT віддав 200 без ключа 'articles' після {attempts} спроб "
                    f"(мʼякий троттл ліміту запитів, НЕ 'немає новин'): "
                    f"{response.text[:500]!r}"
                )

            return payload

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
