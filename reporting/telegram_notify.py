#!/usr/bin/env python3
"""
Мінімальне сповіщення в Telegram про останнє зібране значення показника.

Це НЕ "короткий регулярний звіт" з reporting/CLAUDE.md (той з'явиться
у Фазі 4, коли буде що агрегувати з analysis/) — це технічна перевірка
критерію завершення Фази 0: дані реально дійшли від збору до
користувача. Тому тут тільки форматування вже збереженого факту,
жодної інтерпретації "добре це чи погано".

Використання:
    python telegram_notify.py --metric cpi
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
import requests

# data-ingestion не є валідним іменем Python-пакета (дефіс у назві),
# тож додаємо його вміст напряму в sys.path, щоб дістати common.db.
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data-ingestion")
)
from common.db import get_connection, fetch_latest  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

# Людські підписи для показників — суто для форматування повідомлення,
# не аналітика.
METRIC_LABELS = {
    "cpi": "CPI (інфляція, США)",
    "fed_funds_rate": "Fed Funds Rate",
    "unemployment_rate": "Рівень безробіття (США)",
    "core_cpi": "Core CPI (без їжі/енергії, США)",
    "pce_price_index": "PCE Price Index (орієнтир ФРС)",
    "nonfarm_payrolls": "Non-Farm Payrolls (США)",
    "treasury_10y": "10Y Treasury Yield (США)",
    "treasury_2y": "2Y Treasury Yield (США)",
    "initial_jobless_claims": "Initial Jobless Claims (США)",
    "real_gdp": "Real GDP (США)",
    "retail_sales": "Retail Sales (США)",
    "housing_starts": "Housing Starts (США)",
    "mortgage_rate_30y": "30Y Fixed Mortgage Rate (США)",
    "eurozone_hicp": "HICP (інфляція, єврозона)",
    "eurozone_deposit_rate": "Deposit Facility Rate (єврозона)",
    "eurozone_unemployment_rate": "Рівень безробіття (єврозона)",
}

# metric_id → джерело, для автовизначення --source, якщо не задано явно.
# Дублює розподіл із data-ingestion/run_collect.py:ADAPTERS — тримаємо
# тут окремо (без прямого імпорту), бо reporting/ і data-ingestion/ —
# незалежні контейнери/деплойменти (див. reporting/CLAUDE.md).
_METRIC_SOURCE = {
    "cpi": "fred", "fed_funds_rate": "fred", "unemployment_rate": "fred",
    "core_cpi": "fred", "pce_price_index": "fred", "nonfarm_payrolls": "fred",
    "treasury_10y": "fred", "treasury_2y": "fred", "initial_jobless_claims": "fred",
    "real_gdp": "fred", "retail_sales": "fred", "housing_starts": "fred",
    "mortgage_rate_30y": "fred",
    "eurozone_hicp": "ecb", "eurozone_deposit_rate": "ecb",
    "eurozone_unemployment_rate": "ecb",
}


def format_message(row: dict, metric_id: str) -> str:
    label = METRIC_LABELS.get(metric_id, metric_id)
    return (
        f"📊 {label}\n"
        f"Значення: {row['value']}\n"
        f"За період: {row['observed_at']}\n"
        f"Джерело: {row['source']} (ревізія {row['revision']})\n"
        f"Зібрано: {row['fetched_at']}"
    )


def send_telegram_message(token: str, chat_id: str, text: str) -> dict:
    url = TELEGRAM_API_URL.format(token=token)
    response = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=15)
    response.raise_for_status()
    return response.json()


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metric", required=True, help="metric_id, напр. cpi")
    parser.add_argument(
        "--source", default=None,
        help="за замовчуванням визначається автоматично за --metric",
    )
    args = parser.parse_args()

    source = args.source or _METRIC_SOURCE.get(args.metric)
    if source is None:
        logger.error(
            "Невідомий metric_id %r і --source не задано явно. "
            "Додайте metric_id у _METRIC_SOURCE або вкажіть --source.",
            args.metric,
        )
        sys.exit(1)

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error(
            "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не задані в .env (див. .env.example)"
        )
        sys.exit(1)

    conn = get_connection()
    try:
        row = fetch_latest(conn, source=source, metric_id=args.metric)
    finally:
        conn.close()

    if row is None:
        logger.warning(
            "Немає даних для %s/%s — спершу запустіть "
            "data-ingestion/run_collect.py --metric %s",
            source, args.metric, args.metric,
        )
        sys.exit(1)

    text = format_message(row, args.metric)
    send_telegram_message(token, chat_id, text)
    logger.info("Надіслано в Telegram: %s", text.splitlines()[0])


if __name__ == "__main__":
    main()
