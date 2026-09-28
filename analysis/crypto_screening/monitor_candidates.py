#!/usr/bin/env python3
"""
Погодинний моніторинг кандидатів на SHORT/WATCH
(crypto_screening_candidates) — продовження run_screening.py (денний
скан заводить кандидата, щойно бачить памп ≥30%; ця джоба оновлює його
щогодини). Пряма вимога користувача (2026-09-27): денного відбору (1д)
досить для широкого сканування ринку, але для самого стеження за
шиткоїнами-кандидатами на шорт — занадто повільно, потрібно 1г.

На відміну від run_screening.py (увесь ринок, Tier A), тут — ЛИШЕ
активні кандидати (зазвичай одиниці-десятки, не тисячі) — дешево,
можна щогодини без навантаження на API.

**Дельта без фіксованого вікна годин:** OI/обсяг порівнюються не за
"останні N годин", а з тим, що зафіксовано МИНУЛОГО разу
(`last_oi_usd`/`last_quote_volume` у самому рядку кандидата) — пряма
вказівка користувача: "тримати монету в статусі, поки дані
відповідають", без таймера. Перший прогін після додавання кандидата
дельту порахувати не може (немає "минулого разу") — це очікувано, не
помилка.

**Коли кандидат закривається (`status='closed'`):** памп більше не
тримається (поточний памп впав нижче порогу) або символ зник із
агрегованого знімку (делістинг/тимчасова відсутність на всіх біржах).
Доки памп тримається, кандидат лишається активним незалежно від
результату SHORT/WATCH-перевірки (просто продовжує спостерігатись).

Використання:
    python monitor_candidates.py
"""

import logging
import os
import sys

import requests
from dotenv import load_dotenv

_ANALYSIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ANALYSIS_DIR, "..", "data-ingestion"))
sys.path.insert(0, _ANALYSIS_DIR)

from common.db import get_connection  # noqa: E402

from crypto.binance_futures_adapter import fetch_market_snapshot as fetch_binance_snapshot  # noqa: E402
from crypto.bybit_futures_adapter import fetch_market_snapshot as fetch_bybit_snapshot  # noqa: E402
from crypto.okx_futures_adapter import fetch_market_snapshot as fetch_okx_snapshot  # noqa: E402

from crypto_screening.aggregate_sources import aggregate_snapshots  # noqa: E402
from crypto_screening.short_watch_screen import screen_short_or_watch, PUMP_THRESHOLD_PCT  # noqa: E402
from crypto_screening._candidates_db import fetch_active_candidates, update_candidate  # noqa: E402
from crypto_screening.run_screening import (  # noqa: E402
    _pct_change,
    compute_price_indicators,
    pump_pct_from_aggregated,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def monitor_once(conn, session: requests.Session) -> dict[str, int]:
    counts = {"short": 0, "watch": 0, "candidate": 0, "closed": 0}

    candidates = fetch_active_candidates(conn)
    if not candidates:
        logger.info("Активних кандидатів немає")
        return counts

    aggregated = aggregate_snapshots(
        fetch_binance_snapshot(session), fetch_bybit_snapshot(session), fetch_okx_snapshot(session)
    )

    for candidate in candidates:
        symbol = candidate["symbol"]
        try:
            data = aggregated.get(symbol)
            if data is None:
                logger.warning("%s: зник з агрегованого знімку — закриваю", symbol)
                update_candidate(conn, candidate["id"], "closed", None, None, None, None, "символ зник із ринку")
                counts["closed"] += 1
                continue

            pump_pct = pump_pct_from_aggregated(data)
            if pump_pct is None or pump_pct < PUMP_THRESHOLD_PCT:
                update_candidate(
                    conn, candidate["id"], "closed", pump_pct, data["funding_rate_avg"],
                    data["open_interest_usd"], data["quote_volume_24h"],
                    "памп вичерпався — нижче порогу",
                )
                counts["closed"] += 1
                continue

            # Дельта "з минулого разу" — не за фіксоване вікно годин
            # (докладніше docstring модуля). None у першому прогоні
            # після додавання кандидата — очікувано, не помилка.
            oi_change_pct = None
            if candidate["last_oi_usd"] is not None and data["open_interest_usd"] is not None:
                oi_change_pct = _pct_change(float(candidate["last_oi_usd"]), float(data["open_interest_usd"]))

            volume_spike_pct = None
            if candidate["last_quote_volume"] is not None and data["quote_volume_24h"] is not None:
                volume_spike_pct = _pct_change(float(candidate["last_quote_volume"]), float(data["quote_volume_24h"]))

            price = compute_price_indicators(session, symbol)

            signal = screen_short_or_watch(
                symbol=symbol,
                pump_pct=pump_pct,
                oi_change_pct_after_pump=oi_change_pct,
                volume_spike_pct=volume_spike_pct,
                rsi_value=price["rsi"],
                funding_rate=data["funding_rate_avg"],
            )

            # "none" -> памп ще тримається, але критерії SHORT/WATCH ще
            # не підтвердились — лишається 'candidate' (далі спостерігаємо),
            # НЕ закривається (закриття — лише коли сам памп вичерпався, вище).
            new_status = signal.category if signal.category != "none" else "candidate"
            update_candidate(
                conn, candidate["id"], new_status, pump_pct, data["funding_rate_avg"],
                data["open_interest_usd"], data["quote_volume_24h"],
                "; ".join(signal.reasons),
            )
            counts[new_status] += 1
            logger.info("%s: %s — %s", symbol, new_status, "; ".join(signal.reasons))
        except Exception:
            logger.error("%s: моніторинг провалився", symbol, exc_info=True)

    return counts


def main() -> None:
    load_dotenv()

    conn = get_connection()
    try:
        counts = monitor_once(conn, requests.Session())
    finally:
        conn.close()

    logger.info(
        "Готово: %d short, %d watch, %d candidate (далі спостерігаємо), %d closed",
        counts["short"], counts["watch"], counts["candidate"], counts["closed"],
    )


if __name__ == "__main__":
    main()
