"""
Спільна LLM-"проводка" для всіх аналітичних скриптів analysis/, що
викликають модель: вибір провайдера, сам виклик, розбір структурованої
відповіді, обов'язковий аудит-лог виклику (rule 5 кореневого CLAUDE.md).

## Чому цей модуль існує (зміна рішення, 2026-09-27)

Раніше `SynthesisResult`/`SynthesisResponseError`/`parse_response()`/
`call_llm()`/`log_llm_call()` були СВІДОМО дубльовані в кожному
LLM-скрипті ("кожен скрипт самодостатній", docs/decisions.md
2026-09-27). За чотирма скриптами (`news_analysis/synthesize.py`,
`news_analysis/synthesize_market.py`, `news_analysis/discover_candidates.py`,
`expectations/synthesize.py`) це стало ~150 рядків байт-у-байт копій,
а головне — перехід на Anthropic (CLAUDE.md: "Anthropic API фінальний
висновок аналіз") вимагав би однакової правки в чотирьох місцях, де
легко пропустити одне. Тепер провайдер перемикається В ОДНОМУ місці —
`call_llm()` нижче.

Що НЕ винесено сюди (залишається в кожному скрипті, бо справді різне):
`SYSTEM_PROMPT`, `build_prompt()` і форма результату, коли вона інша
(`discover_candidates.py` віддає список кандидатів, не
`SynthesisResult`; `relevance_filter.py` — `NewsAnalysisResult` з
`is_relevant`/`asset_id`).

## Провайдер

`SYNTHESIS_LLM_PROVIDER` (.env, дефолт "deepseek") читається НА МОМЕНТ
ВИКЛИКУ, не при імпорті модуля — інакше значення "замерзало" на стані
env під час імпорту (у тестах це вимагало monkeypatch константи в
кожному модулі окремо). Anthropic — свідомо ще не реалізовано, клієнт
з'явиться разом із самим переходом (docs/decisions.md, 2026-09-27).
"""

import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Optional

from news_analysis.deepseek_client import call_deepseek

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "deepseek"

# Спільний словник напрямків сигналу для ВСІХ LLM-виходів проєкту
# (analysis/CLAUDE.md "Формат виходу LLM-аналізу") — і синтезу тут, і
# класифікації окремої статті (`relevance_filter.py` імпортує звідси).
DIRECTIONS = frozenset({"up", "down", "neutral", "unclear"})

# Мінімум полів структурованого висновку синтезу (той самий контракт з
# analysis/CLAUDE.md; `source_refs` приєднує код, не LLM — ризик
# галюцинації того, що й так відоме викликачу).
SYNTHESIS_FIELDS = ("direction", "confidence", "summary", "reasoning")


@dataclass
class SynthesisResult:
    direction: str
    confidence: float
    summary: str
    reasoning: str


class SynthesisResponseError(ValueError):
    pass


def resolve_provider() -> str:
    """Поточний провайдер LLM — читається з env щоразу (див. докстрінг
    модуля, розділ "Провайдер")."""
    return os.environ.get("SYNTHESIS_LLM_PROVIDER") or DEFAULT_PROVIDER


def api_key_env_for(provider: str) -> Optional[str]:
    """Назва env-змінної з ключем для провайдера, або None якщо ключ не
    потрібен. Окремо від `require_api_key()`, щоб перелік провайдерів
    жив в одному місці."""
    return {"deepseek": "DEEPSEEK_API_KEY"}.get(provider)


def require_api_key() -> Optional[str]:
    """Ключ поточного провайдера або вихід із кодом 1 і зрозумілим
    повідомленням — той самий early-exit, що був скопійований у main()
    кожного LLM-скрипта."""
    provider = resolve_provider()
    env_name = api_key_env_for(provider)
    if env_name is None:
        logger.error(
            "Непідтримуваний SYNTHESIS_LLM_PROVIDER=%r — наразі реалізовано лише "
            "'deepseek' (Anthropic-клієнт з'явиться разом зі свідомим переходом, "
            "docs/decisions.md, 2026-09-27).",
            provider,
        )
        sys.exit(1)

    api_key = os.environ.get(env_name)
    if not api_key:
        logger.error("%s не задано. Додайте його в .env (див. .env.example).", env_name)
        sys.exit(1)
    return api_key


def call_llm(prompt: str, system_prompt: str, api_key: str) -> str:
    """ЄДИНЕ місце, де вибирається провайдер LLM для всього analysis/ —
    саме тут з'явиться Anthropic-гілка при переході."""
    provider = resolve_provider()
    if provider == "deepseek":
        return call_deepseek(prompt, api_key=api_key, system_prompt=system_prompt)
    raise ValueError(
        f"Непідтримуваний SYNTHESIS_LLM_PROVIDER={provider!r} — наразі реалізовано "
        "лише 'deepseek' (Anthropic-клієнт з'явиться разом зі свідомим переходом, "
        "docs/decisions.md, 2026-09-27)."
    )


def parse_json_object(raw_content: str, error_class: type = SynthesisResponseError) -> dict:
    """JSON-об'єкт із сирої відповіді LLM. `error_class` — щоб
    скрипт з іншою формою виходу (`discover_candidates.py`) кидав свій
    власний тип помилки, не синтезний."""
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise error_class(f"Відповідь LLM не є коректним JSON: {raw_content!r}") from e
    if not isinstance(data, dict):
        raise error_class(f"Відповідь LLM не є JSON-об'єктом: {raw_content!r}")
    return data


def parse_confidence(value, error_class: type = SynthesisResponseError) -> float:
    """confidence як число в [0,1] — спільна валідація для синтезу й
    для класифікації окремої статті (`relevance_filter.py`)."""
    try:
        confidence = float(value)
    except (TypeError, ValueError) as e:
        raise error_class(f"confidence не число: {value!r}") from e
    if not 0 <= confidence <= 1:
        raise error_class(f"confidence поза межами [0,1]: {confidence}")
    return confidence


def parse_synthesis_response(raw_content: str) -> SynthesisResult:
    """Розбір структурованого висновку синтезу — спільний для
    news_analysis/synthesize.py, news_analysis/synthesize_market.py і
    expectations/synthesize.py (усі троє мають ІДЕНТИЧНИЙ контракт
    виходу, різняться лише промптом)."""
    data = parse_json_object(raw_content)

    missing = [f for f in SYNTHESIS_FIELDS if f not in data]
    if missing:
        raise SynthesisResponseError(f"У відповіді LLM бракує полів {missing}: {data!r}")

    direction = data["direction"]
    if direction not in DIRECTIONS:
        raise SynthesisResponseError(f"Неочікуване значення direction: {direction!r}")

    return SynthesisResult(
        direction=direction,
        confidence=parse_confidence(data["confidence"]),
        summary=data["summary"],
        reasoning=data["reasoning"],
    )


def log_llm_call(
    conn, provider: str, purpose: str, prompt: str, response: str, source_ref: Optional[str]
) -> int:
    """Обов'язковий аудит-лог виклику LLM (rule 5 кореневого CLAUDE.md:
    промпт + відповідь + timestamp + джерело).

    SQL живе тут, а не в `<пакет>/_db.py`, бо `llm_call_log` — не
    таблиця конкретного пакета, а спільний журнал ВСІХ LLM-викликів
    проєкту: раніше один і той самий INSERT був продубльований у
    `news_analysis/_db.py` і `expectations/_db.py`. Один писар — одна
    копія SQL."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO llm_call_log (provider, purpose, prompt, response, source_ref)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (provider, purpose, prompt, response, source_ref),
        )
        llm_call_id = cur.fetchone()[0]
    conn.commit()
    return llm_call_id
