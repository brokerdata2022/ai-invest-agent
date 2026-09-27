#!/usr/bin/env python3
"""
LLM-синтез "новини + ціна" по активу (docs/news-purpose.md, "Ціль 1" —
точки входу для watchlist-пар): зводить уже готовий новинний сигнал
(aggregate.py:AssetSignal) з ціновим рухом за те саме вікно
(prices.py:PriceChange) в один причинний висновок — чи рух ціни
пояснюється новинами (схоже на тренд), чи новин немає/суперечать
(схоже на шум/корекцію).

Межа шарів (rule 1, CLAUDE.md): тут вирішується, ЩО означає зіставлення
факту й новин — aggregate.py/prices.py лишаються звичайним кодом без
LLM (analysis/CLAUDE.md).

Формат виходу — analysis/CLAUDE.md "Формат виходу LLM-аналізу":
summary/direction/confidence/reasoning від LLM; source_refs — той самий
принцип, що relevance_filter.py: DeepSeek його не генерує (ризик
галюцинації того, що й так відоме викликачу з `signal.summaries`), код
приєднує сам.

Провайдер (docs/decisions.md, 2026-09-27): DeepSeek під час розробки
(дешевше для ітерацій), Anthropic — перед завершенням фічі. Один
env-параметр SYNTHESIS_LLM_PROVIDER, дефолт "deepseek" — заміна без
редагування коду логіки синтезу.

Обсяг: тільки активи, для яких є ОБИДВА входи (новинний сигнал і ціна,
prices.py:ASSET_PRICE_SOURCES) — активи з сигналом, але без цінового
джерела (xagusd/btc/eth/sol, тикери акцій зі скринінгу) пропускаються.

Використання:
    python synthesize.py
    python synthesize.py --stream watchlist --max-age-days 3
"""

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv
import requests

_ANALYSIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ANALYSIS_DIR)
sys.path.insert(0, os.path.join(_ANALYSIS_DIR, "..", "data-ingestion"))

from common.db import get_connection  # noqa: E402
from news_analysis._db import fetch_relevant_for_aggregation, log_llm_call, save_synthesis  # noqa: E402
from news_analysis.aggregate import AssetSignal, aggregate_by_asset, cluster_articles  # noqa: E402
from news_analysis.deepseek_client import call_deepseek  # noqa: E402
from news_analysis.prices import PriceChange, fetch_all_price_changes  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_DIRECTIONS = frozenset({"up", "down", "neutral", "unclear"})
_REQUIRED_FIELDS = ("direction", "confidence", "summary", "reasoning")

# Заміна на "anthropic" пізніше — окремий клієнт-модуль ще не написаний
# (YAGNI: писати його заздалегідь, без реального переходу, немає сенсу).
LLM_PROVIDER = os.environ.get("SYNTHESIS_LLM_PROVIDER", "deepseek")

SYSTEM_PROMPT = (
    "Ти фінансовий аналітик. Тобі дають один актив: агрегований "
    "новинний сигнал за останні дні (скільки НЕЗАЛЕЖНИХ історій "
    "(дублікати з різних видань уже об'єднані), який напрямок у "
    "кожної, короткі факти з них) і фактичну зміну ціни цього активу "
    "за той самий період."
    "\n\n"
    "Твоя задача — причинна атрибуція: чи рух ціни ПОЯСНЮЄТЬСЯ "
    "новинним сигналом (напрямок новин збігається з напрямком ціни, "
    "є конкретні факти-причини — це більше схоже на фундаментально "
    "обґрунтований тренд), чи новин немає, вони суперечать руху ціни, "
    "чи занадто нечіткі (це більше схоже на шум/технічну корекцію). "
    "Кількість незалежних історій — природна міра сили сигналу: одна "
    "стаття важить менше, ніж та сама новина в кількох джерелах."
    "\n\n"
    "НІКОЛИ не давай прямих торгових рекомендацій ('купити'/'продати'/"
    "'входити в позицію') — тільки описові характеристики. Відповідай "
    "ЛИШЕ JSON-об'єктом з полями: direction (одне з: up, down, neutral, "
    "unclear — твоя оцінка напрямку РИЗИКУ для активу з урахуванням "
    "обох входів, не просто напрямок ціни), confidence (число від 0 до "
    "1 — наскільки новини й ціна узгоджуються), summary (1-2 речення: "
    "тренд чи шум, і чому), reasoning (коротке обґрунтування для "
    "аудиту)."
)


@dataclass
class SynthesisResult:
    direction: str
    confidence: float
    summary: str
    reasoning: str


class SynthesisResponseError(ValueError):
    pass


def build_prompt(asset_id: str, signal: AssetSignal, price: PriceChange) -> str:
    lines = [
        f"Актив: {asset_id}",
        f"Новинний сигнал за вікно: {signal.cluster_count} незалежних історій, "
        f"напрямки {dict(signal.direction_counts)}, net_lean={signal.net_lean:+d}",
        f"Зміна ціни за той самий період ({price.start_date} → {price.end_date}): "
        f"{price.pct_change:.2f}% ({price.start_value} → {price.end_value})",
    ]
    if signal.summaries:
        lines.append("Факти з новин:")
        for s in signal.summaries[:10]:
            lines.append(f"- {s}")
    return "\n".join(lines)


def parse_response(raw_content: str) -> SynthesisResult:
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise SynthesisResponseError(
            f"Відповідь LLM не є коректним JSON: {raw_content!r}"
        ) from e

    missing = [f for f in _REQUIRED_FIELDS if f not in data]
    if missing:
        raise SynthesisResponseError(f"У відповіді LLM бракує полів {missing}: {data!r}")

    direction = data["direction"]
    if direction not in _DIRECTIONS:
        raise SynthesisResponseError(f"Неочікуване значення direction: {direction!r}")

    try:
        confidence = float(data["confidence"])
    except (TypeError, ValueError) as e:
        raise SynthesisResponseError(f"confidence не число: {data['confidence']!r}") from e
    if not 0 <= confidence <= 1:
        raise SynthesisResponseError(f"confidence поза межами [0,1]: {confidence}")

    return SynthesisResult(
        direction=direction,
        confidence=confidence,
        summary=data["summary"],
        reasoning=data["reasoning"],
    )


def call_llm(prompt: str, system_prompt: str, api_key: str) -> str:
    if LLM_PROVIDER == "deepseek":
        return call_deepseek(prompt, api_key=api_key, system_prompt=system_prompt)
    raise ValueError(
        f"Непідтримуваний SYNTHESIS_LLM_PROVIDER={LLM_PROVIDER!r} — наразі реалізовано "
        "лише 'deepseek' (Anthropic-клієнт з'явиться разом зі свідомим переходом, "
        "docs/decisions.md, 2026-09-27)."
    )


def synthesize_asset(
    asset_id: str, signal: AssetSignal, price: PriceChange, api_key: str
) -> tuple[SynthesisResult, str, str]:
    """Будує промпт → LLM → парсить. Повертає (результат, промпт,
    сира_відповідь) — обов'язкові для логування в llm_call_log
    (rule 5), той самий контракт, що relevance_filter.analyze_article()."""
    prompt = build_prompt(asset_id, signal, price)
    raw_content = call_llm(prompt, SYSTEM_PROMPT, api_key)
    result = parse_response(raw_content)
    return result, prompt, raw_content


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", choices=["watchlist", "general", "geopolitical"], default=None)
    parser.add_argument("--max-age-days", type=int, default=7)
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY") if LLM_PROVIDER == "deepseek" else None
    if LLM_PROVIDER == "deepseek" and not api_key:
        logger.error("DEEPSEEK_API_KEY не задано. Додайте його в .env (див. .env.example).")
        sys.exit(1)

    conn = get_connection()
    try:
        articles = fetch_relevant_for_aggregation(
            conn, stream=args.stream, max_age_days=args.max_age_days
        )
        clusters = cluster_articles(articles)
        signals = aggregate_by_asset(clusters)
        logger.info("%d активів із новинним сигналом", len(signals))

        prices = fetch_all_price_changes(conn, list(signals), days=args.max_age_days)

        synthesized = 0
        for asset_id, signal in signals.items():
            price = prices.get(asset_id)
            if price is None:
                logger.info("%s: немає цінового джерела/даних за вікно — пропущено", asset_id)
                continue

            try:
                result, prompt, raw_content = synthesize_asset(asset_id, signal, price, api_key)
            except SynthesisResponseError:
                logger.exception("%s: некоректна відповідь LLM — пропущено", asset_id)
                continue
            except requests.exceptions.RequestException:
                logger.exception("%s: мережева помилка виклику LLM — пропущено", asset_id)
                continue

            llm_call_id = log_llm_call(
                conn,
                provider=LLM_PROVIDER,
                purpose="news_price_synthesis",
                prompt=prompt,
                response=raw_content,
                source_ref=asset_id,
            )
            save_synthesis(
                conn,
                asset_id=asset_id,
                signal=signal,
                price=price,
                window_days=args.max_age_days,
                result=result,
                llm_call_id=llm_call_id,
            )
            synthesized += 1
            logger.info(
                "%s → direction=%s confidence=%.2f: %s",
                asset_id, result.direction, result.confidence, result.summary,
            )
    finally:
        conn.close()

    logger.info("Готово: %d активів синтезовано", synthesized)


if __name__ == "__main__":
    main()
