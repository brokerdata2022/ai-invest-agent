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

Межа шарів / формат виходу — той самий принцип, що
news_analysis/synthesize.py; провайдер (SYNTHESIS_LLM_PROVIDER, дефолт
"deepseek"), розбір відповіді й аудит-лог виклику — спільний код
`llm_common.py`, тут лишається тільки своє: SYSTEM_PROMPT і
build_prompt().

Використання (після analysis/expectations/compare_releases.py):
    python synthesize.py
    python synthesize.py --limit 5
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
import requests

_ANALYSIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ANALYSIS_DIR)
sys.path.insert(0, os.path.join(_ANALYSIS_DIR, "..", "data-ingestion"))

from common.db import get_connection  # noqa: E402
from llm_common import (  # noqa: E402
    SynthesisResponseError,
    call_llm,
    log_llm_call,
    parse_synthesis_response,
    require_api_key,
    resolve_provider,
)

from expectations._db import fetch_unsynthesized_comparisons, save_synthesis  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

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


def synthesize_comparison(comparison: dict, api_key: str):
    """Будує промпт → LLM → парсить. Повертає (результат, промпт,
    сира_відповідь) — обов'язкові для логування в llm_call_log
    (rule 5), той самий контракт, що news_analysis/synthesize.py."""
    prompt = build_prompt(comparison)
    raw_content = call_llm(prompt, SYSTEM_PROMPT, api_key)
    result = parse_synthesis_response(raw_content)
    return result, prompt, raw_content


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    api_key = require_api_key()

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
                provider=resolve_provider(),
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
