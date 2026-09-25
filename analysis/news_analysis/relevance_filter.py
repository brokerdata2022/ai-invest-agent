"""
LLM-фільтрація релевантності новин через DeepSeek.

Межа шарів (rule 1, CLAUDE.md): це місце, де вирішується, чи новина
важлива і що вона означає — data-ingestion/news/ тексту не інтерпретує,
тільки збирає (докладніше docs/decisions.md, 2026-09-25).

Формат виходу — analysis/CLAUDE.md "Формат виходу LLM-аналізу":
summary/direction/confidence/reasoning обов'язкові. source_refs тут —
сама стаття (raw_news_id одразу відомий викликачу з БД), тому DeepSeek
його не генерує — ризик галюцинації для того, що й так відоме.

build_prompt()/parse_response() — чисті функції, тестуються на
фейкових прикладах без мережі. analyze_article() — наскрізний виклик,
що ходить у DeepSeek (тестується окремо/мокається).
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

from news_analysis.deepseek_client import call_deepseek

logger = logging.getLogger(__name__)

_DIRECTIONS = frozenset({"up", "down", "neutral", "unclear"})
_REQUIRED_FIELDS = ("is_relevant", "direction", "confidence", "summary", "reasoning")

SYSTEM_PROMPT = (
    "Ти фінансовий новинний аналітик. Тобі дають одну новинну статтю "
    "(заголовок, дата публікації, потік watchlist/general/geopolitical, "
    "опційно список уже відстежуваних активів). Оціни лише релевантність "
    "і дай короткий структурований висновок. НІКОЛИ не давай прямих "
    "торгових рекомендацій ('купити'/'продати'/'входити в позицію') — "
    "тільки описові характеристики. Відповідай ЛИШЕ JSON-об'єктом з "
    "полями: is_relevant (bool — чи стаття може вплинути на ціну "
    "активу чи загальний ринковий сентимент), asset_id (string або "
    "null — тикер/ідентифікатор активу зі списку відстежуваних, якщо "
    "стаття прямо про нього, інакше null), direction (одне з: up, "
    "down, neutral, unclear), confidence (число від 0 до 1), summary "
    "(1-2 речення), reasoning (коротке обґрунтування)."
)


@dataclass
class NewsAnalysisResult:
    is_relevant: bool
    asset_id: Optional[str]
    direction: str
    confidence: float
    summary: str
    reasoning: str


class DeepSeekResponseError(ValueError):
    pass


def build_prompt(article: dict, stream: str, tracked_assets: Optional[list[str]] = None) -> str:
    lines = [
        f"Потік: {stream}",
        f"Заголовок: {article['title']}",
        f"Дата публікації: {article['published_at']}",
        f"URL: {article['url']}",
    ]
    if tracked_assets:
        lines.append(f"Відстежувані активи: {', '.join(tracked_assets)}")
    return "\n".join(lines)


def parse_response(raw_content: str) -> NewsAnalysisResult:
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise DeepSeekResponseError(
            f"Відповідь DeepSeek не є коректним JSON: {raw_content!r}"
        ) from e

    missing = [f for f in _REQUIRED_FIELDS if f not in data]
    if missing:
        raise DeepSeekResponseError(f"У відповіді DeepSeek бракує полів {missing}: {data!r}")

    direction = data["direction"]
    if direction not in _DIRECTIONS:
        raise DeepSeekResponseError(f"Неочікуване значення direction: {direction!r}")

    try:
        confidence = float(data["confidence"])
    except (TypeError, ValueError) as e:
        raise DeepSeekResponseError(f"confidence не число: {data['confidence']!r}") from e
    if not 0 <= confidence <= 1:
        raise DeepSeekResponseError(f"confidence поза межами [0,1]: {confidence}")

    return NewsAnalysisResult(
        is_relevant=bool(data["is_relevant"]),
        asset_id=data.get("asset_id") or None,
        direction=direction,
        confidence=confidence,
        summary=data["summary"],
        reasoning=data["reasoning"],
    )


def analyze_article(
    article: dict,
    stream: str,
    api_key: str,
    tracked_assets: Optional[list[str]] = None,
) -> tuple[NewsAnalysisResult, str, str]:
    """Будує промпт → DeepSeek → парсить. Повертає (результат, промпт,
    сира_відповідь) — прompt/сира відповідь потрібні викликаючому коду
    для обов'язкового логування в llm_call_log (rule 5); ця функція без
    побічних ефектів у БД, як і адаптери в data-ingestion."""
    prompt = build_prompt(article, stream, tracked_assets)
    raw_content = call_deepseek(prompt, api_key=api_key, system_prompt=SYSTEM_PROMPT)
    result = parse_response(raw_content)
    return result, prompt, raw_content
