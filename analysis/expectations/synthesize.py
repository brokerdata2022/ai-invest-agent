#!/usr/bin/env python3
"""
LLM-синтез причинного висновку "факт vs очікування" (docs/status.md,
"наступний крок Фази 2"): бере вже готовий детермінований сюрприз
(compare_releases.py:expectation_comparisons) і формує людський
висновок "вийшло X, очікувалось Y, це означає Z" — критерій завершення
Фази 2 (PLAN.md).

Межа шарів (rule 1, CLAUDE.md; analysis/CLAUDE.md "детермінований vs
LLM"): сам сюрприз (surprise/surprise_pct) уже порахований звичайним
кодом у compare_releases.py — тут LLM лише ІНТЕРПРЕТУЄ готове число, не
рахує його заново.

Формат виходу — analysis/CLAUDE.md "Формат виходу LLM-аналізу":
summary/direction/confidence/reasoning від LLM; source_refs (сам
показник/метод порівняння, на якому базується висновок) приєднує код,
не LLM — той самий принцип, що news_analysis/synthesize.py.

Межа шарів / формат виходу / провайдер — той самий принцип, що
news_analysis/synthesize.py (SynthesisResult/parse_response/call_llm
дубльовані навмисно, кожен LLM-скрипт самодостатній,
docs/decisions.md 2026-09-27 "LLM-синтез новин").

Провайдер: SYNTHESIS_LLM_PROVIDER (спільний з news_analysis/synthesize.py
— один архітектурний перемикач на весь проєкт, docs/decisions.md
2026-09-27), дефолт "deepseek".

Використання (після analysis/expectations/compare_releases.py):
    python synthesize.py
    python synthesize.py --limit 5
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
from news_analysis.deepseek_client import call_deepseek  # noqa: E402

from expectations._db import (  # noqa: E402
    fetch_unsynthesized_comparisons,
    log_llm_call,
    save_synthesis,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_DIRECTIONS = frozenset({"up", "down", "neutral", "unclear"})
_REQUIRED_FIELDS = ("direction", "confidence", "summary", "reasoning")

LLM_PROVIDER = os.environ.get("SYNTHESIS_LLM_PROVIDER", "deepseek")

SYSTEM_PROMPT = (
    "Ти макро-аналітик. Тобі дають один макроекономічний реліз: яке "
    "фактичне значення вийшло, яке було ринкове очікування (прогноз), "
    "і вже порахований числовий сюрприз (факт мінус очікування, у тих "
    "самих приведених одиницях і, якщо доступно, у відсотках від "
    "очікування)."
    "\n\n"
    "Твоя задача — коротко пояснити, ЩО ЦЕ ОЗНАЧАЄ: наскільки суттєве "
    "це відхилення від очікувань і в який бік (гірше/краще з точки "
    "зору відповідного тренду — інфляція/зайнятість/зростання/ставки), "
    "і який напрямок ринкового сигналу для пов'язаної валюти/активу це "
    "імовірно означає."
    "\n\n"
    "НІКОЛИ не давай прямих торгових рекомендацій ('купити'/'продати'/"
    "'входити в позицію') — тільки описові характеристики. Відповідай "
    "ЛИШЕ JSON-об'єктом з полями: direction (одне з: up, down, neutral, "
    "unclear — напрямок ринкового сигналу, не просто знак сюрпризу), "
    "confidence (число від 0 до 1 — наскільки однозначний висновок), "
    "summary (1-2 речення у форматі 'вийшло X, очікувалось Y, це "
    "означає Z'), reasoning (коротке обґрунтування для аудиту)."
)


@dataclass
class SynthesisResult:
    direction: str
    confidence: float
    summary: str
    reasoning: str


class SynthesisResponseError(ValueError):
    pass


def build_prompt(comparison: dict) -> str:
    lines = [
        f"Показник: {comparison['metric_id']} ({comparison['source']})",
        f"Дата спостереження: {comparison['observed_at']}",
        f"Рівень впливу релізу: {comparison['impact_level']}",
        f"Метод приведення до спільних одиниць: {comparison['comparison_method']}",
        f"Факт: {float(comparison['actual_value']):.4g}",
        f"Очікування (прогноз, приведений до тих самих одиниць): "
        f"{float(comparison['expected_value_parsed']):.4g} "
        f"(оригінальний текст прогнозу: {comparison['expected_value_raw']})",
        f"Сюрприз (факт - очікування): {float(comparison['surprise']):+.4g}",
    ]
    if comparison.get("surprise_pct") is not None:
        lines.append(
            f"Сюрприз у % від очікування: {float(comparison['surprise_pct']):+.2f}%"
        )
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


def synthesize_comparison(comparison: dict, api_key: str) -> tuple[SynthesisResult, str, str]:
    """Будує промпт → LLM → парсить. Повертає (результат, промпт,
    сира_відповідь) — обов'язкові для логування в llm_call_log
    (rule 5), той самий контракт, що news_analysis/synthesize.py."""
    prompt = build_prompt(comparison)
    raw_content = call_llm(prompt, SYSTEM_PROMPT, api_key)
    result = parse_response(raw_content)
    return result, prompt, raw_content


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY") if LLM_PROVIDER == "deepseek" else None
    if LLM_PROVIDER == "deepseek" and not api_key:
        logger.error("DEEPSEEK_API_KEY не задано. Додайте його в .env (див. .env.example).")
        sys.exit(1)

    conn = get_connection()
    try:
        comparisons = fetch_unsynthesized_comparisons(conn, limit=args.limit)
        logger.info("%d порівнянь без синтезу", len(comparisons))

        synthesized = 0
        for comparison in comparisons:
            try:
                result, prompt, raw_content = synthesize_comparison(comparison, api_key)
            except SynthesisResponseError:
                logger.exception(
                    "%s: некоректна відповідь LLM — пропущено", comparison["metric_id"]
                )
                continue
            except requests.exceptions.RequestException:
                logger.exception(
                    "%s: мережева помилка виклику LLM — пропущено", comparison["metric_id"]
                )
                continue

            llm_call_id = log_llm_call(
                conn,
                provider=LLM_PROVIDER,
                purpose="expectation_synthesis",
                prompt=prompt,
                response=raw_content,
                source_ref=str(comparison["comparison_id"]),
            )
            source_refs = [{
                "metric_id": comparison["metric_id"],
                "source": comparison["source"],
                "observed_at": str(comparison["observed_at"]),
                "comparison_method": comparison["comparison_method"],
            }]
            save_synthesis(
                conn,
                comparison_id=comparison["comparison_id"],
                result=result,
                source_refs=source_refs,
                llm_call_id=llm_call_id,
            )
            synthesized += 1
            logger.info(
                "%s → direction=%s confidence=%.2f: %s",
                comparison["metric_id"], result.direction, result.confidence, result.summary,
            )
    finally:
        conn.close()

    logger.info("Готово: %d порівнянь синтезовано", synthesized)


if __name__ == "__main__":
    main()
