#!/usr/bin/env python3
"""
Фундаментальний LLM-аналіз акцій (спек користувача 2026-09-28:
"Фундаментальний ШІ-аналіз о 14:00 кожного робочого дня для активів зі
списку обраних") — наскрізний шлях "звітність із БД → LLM →
fundamental_analysis".

Межа покриття, названа честно: у спеку сказано "watchlist + пройшли
скринінг", але у watchlist-активів (золото, нафта, газ, BTC, валютні
пари) фундаменталу НЕ ІСНУЄ — немає ні виручки, ні EPS, ні P/E. Тому
аналізуються лише АКЦІЇ (sec_edgar + screening_results); вдавати, що
товар має фундаментал, було б гірше за чесну межу (db/schema.sql).

Межа шарів (rule 1): цей файл — лише проводка. Промпт і розбір
відповіді — `fundamental_llm.py`, пороги/ліміти — `config.py`, SQL —
`_db.py`.

Використання:
    python run_analysis.py
    python run_analysis.py --top 3
    python run_analysis.py --ticker HPE     # один тикер, для перевірки
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
import requests

_ANALYSIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ANALYSIS_DIR, "..", "data-ingestion"))
sys.path.insert(0, _ANALYSIS_DIR)

from common.db import get_connection  # noqa: E402
from llm_common import (  # noqa: E402
    SynthesisResponseError,
    call_llm,
    log_llm_call,
    require_api_key,
    resolve_provider,
)

from fundamental import config  # noqa: E402
from fundamental._db import (  # noqa: E402
    fetch_fundamental_series,
    fetch_top_stocks,
    save_fundamental_analysis,
)
from fundamental.fundamental_llm import (  # noqa: E402
    SYSTEM_PROMPT,
    build_prompt,
    parse_fundamental_response,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def collect_series(conn, ticker: str) -> tuple[dict, int]:
    """({людська назва: точки}, скільки квартальних точок по виручці) —
    кількість по виручці окремо, бо саме вона вирішує, чи є про що
    говорити (`config.MIN_QUARTERS`)."""
    series: dict[str, list[dict]] = {}
    revenue_points = 0
    for suffix, label in config.FUNDAMENTAL_METRICS:
        points = fetch_fundamental_series(conn, ticker, suffix, config.QUARTERS)
        if points:
            series[label] = points
        if suffix == "revenue":
            revenue_points = len(points)
    return series, revenue_points


def analyze_stock(conn, stock: dict, api_key: str) -> bool:
    """True — аналіз збережено. False — тикер пропущено (замало даних
    або збійна відповідь LLM); причина в лозі."""
    ticker = stock["ticker"]
    series, revenue_points = collect_series(conn, ticker)

    if revenue_points < config.MIN_QUARTERS:
        logger.warning(
            "%s: лише %d квартальних точок виручки (потрібно >= %d) — пропущено",
            ticker, revenue_points, config.MIN_QUARTERS,
        )
        return False

    valuation = {
        "pe": stock.get("pe"),
        "revenue_growth": stock.get("revenue_growth"),
        "eps_growth": stock.get("eps_growth"),
    }
    prompt = build_prompt(ticker, stock.get("company_name"), series, valuation)
    raw_content = call_llm(prompt, SYSTEM_PROMPT, api_key)

    # Аудит-лог ДО розбору (rule 5): збійну відповідь найцікавіше
    # розбирати постфактум, і без запису від неї не лишилось би сліду.
    llm_call_id = log_llm_call(
        conn,
        provider=resolve_provider(),
        purpose="fundamental_analysis",
        prompt=prompt,
        response=raw_content,
        source_ref=ticker,
    )

    result = parse_fundamental_response(raw_content)
    save_fundamental_analysis(
        conn,
        ticker=ticker,
        company_name=stock.get("company_name"),
        result=result,
        inputs={"valuation": valuation, "series": series},
        llm_call_id=llm_call_id,
    )
    logger.info(
        "%s: direction=%s confidence=%.2f (сильних %d, ризиків %d): %s",
        ticker, result.direction, result.confidence,
        len(result.strengths), len(result.risks), result.summary,
    )
    return True


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=config.TOP_N_STOCKS)
    parser.add_argument(
        "--ticker", default=None,
        help="проаналізувати ОДИН тикер замість топу скринінгу (перевірка)",
    )
    args = parser.parse_args()

    api_key = require_api_key()

    conn = get_connection()
    try:
        if args.ticker:
            stocks = [{"ticker": args.ticker.upper(), "company_name": None}]
        else:
            stocks = fetch_top_stocks(conn, args.top)

        if not stocks:
            logger.warning(
                "Скринінг не дав жодного тикера — спершу потрібен прогін "
                "analysis/screening/composite_score.py"
            )
            return

        logger.info("Аналізуємо %d акцій", len(stocks))
        analyzed = 0
        for stock in stocks:
            try:
                if analyze_stock(conn, stock, api_key):
                    analyzed += 1
            except SynthesisResponseError:
                logger.exception("%s: некоректна відповідь LLM — пропущено", stock["ticker"])
                conn.rollback()
            except requests.exceptions.RequestException:
                logger.exception("%s: мережева помилка LLM — пропущено", stock["ticker"])
                conn.rollback()
            except Exception:
                # Один тикер не валить цикл — той самий патерн, що
                # update_forecasts.py/compare_releases.py.
                logger.exception("%s: аналіз провалився", stock["ticker"])
                conn.rollback()

        logger.info("Готово: проаналізовано %d з %d", analyzed, len(stocks))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
