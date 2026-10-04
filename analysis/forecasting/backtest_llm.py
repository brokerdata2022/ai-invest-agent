#!/usr/bin/env python3
"""
Backtest LLM-прогнозу (llm_forecast.py) на історії одного показника —
виконання вимоги analysis/CLAUDE.md "Тестування прогнозних моделей":
кожна модель прогнозування має бути прогоняна на історичних даних, і
критерій "має сенс" — не "працює без помилок", а СТАБІЛЬНО ТОЧНІША за
naive-базову лінію ("нічого не змінилось").

Зміна напрямку на LLM (2026-09-28, рішення користувача) цю вимогу НЕ
скасовує — тільки робить її дорожчою: кожна перевірена точка це окремий
виклик LLM, тому за замовчуванням перевіряється лише `--points 8`
останніх точок (проти `backtest.py`, що безкоштовно проганяє всю
історію лінійною моделлю). Звідси й чесне обмеження висновку: 8 точок —
це індикація, не статистика; великі числа варто набирати свідомо й
рідко.

Честний out-of-sample: на кожній точці в промпт ідуть ЛИШЕ значення ДО
неї, майбутнє не підглядається — той самий принцип, що
`backtest.py:backtest_metric`.

Поруч із LLM міряються ОБИДВІ базові лінії з `trend.py` на тих самих
точках: naive (головний критерій) і лінійний тренд (попередній
напрямок, 2026-09-27) — щоб відповідь на "чи LLM узагалі вартий своїх
грошей" була в одному виводі, без окремого прогону.

Використання:
    python backtest_llm.py --metric cpi
    python backtest_llm.py --metric nonfarm_payrolls --points 12 --min-history 8
"""

import argparse
import logging
import os
import sys
from typing import Callable, Optional

from dotenv import load_dotenv
import requests

_ANALYSIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ANALYSIS_DIR, "..", "data-ingestion"))
sys.path.insert(0, os.path.join(_ANALYSIS_DIR, "..", "monitoring"))
sys.path.insert(0, _ANALYSIS_DIR)

from common.db import get_connection, fetch_recent  # noqa: E402
from llm_common import (  # noqa: E402
    SynthesisResponseError,
    call_llm,
    log_llm_call,
    require_api_key,
    resolve_provider,
)

from forecasting._metric_source import resolve_source  # noqa: E402
from forecasting.llm_forecast import (  # noqa: E402
    SYSTEM_PROMPT,
    build_prompt,
    describe_metric,
    is_plausible,
    parse_forecast_response,
)
from forecasting.trend import linear_trend_forecast, naive_forecast  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_POINTS = 8
DEFAULT_MIN_HISTORY = 6


def _mae(errors: list[float]) -> Optional[float]:
    return sum(errors) / len(errors) if errors else None


def backtest_llm_metric(
    metric_id: str,
    observations_desc: list[dict],
    forecast_fn: Callable[[list[dict]], Optional[float]],
    points: int = DEFAULT_POINTS,
    min_history: int = DEFAULT_MIN_HISTORY,
) -> dict:
    """`observations_desc` — результат fetch_recent() (найновіше перше).
    `forecast_fn(chronological_history) -> прогноз або None` —
    інжектується, щоб ця функція була тестована БЕЗ мережі/LLM (той
    самий прийом, що в тестах решти проєкту: чиста логіка окремо від
    проводки).

    Перевіряються `points` ОСТАННІХ точок історії, для яких попередньої
    історії досить (>= min_history). None-прогноз (збійна відповідь
    LLM) не рахується ні як влучення, ні як промах — точка просто
    пропускається, і це видно в `n_skipped`: мовчазне заниження MAE за
    рахунок "незручних" точок було б гіршим за честний пропуск.

    КРИТИЧНО (виправлено 2026-10-04 після живого прогону
    `unemployment_rate`): пропущена точка виключається і з БАЗОВИХ
    ЛІНІЙ. Спершу було навпаки — naive/тренд рахувались на ВСІХ точках
    "щоб порівнювати на тих самих" — і саме це робило порівняння
    нечесним: набори точок ставали РІЗНИМИ (LLM 7, naive 8). Живий
    кейс: naive отримав "безкоштовну" 8-му точку з похибкою 0 (факт
    4.1 = попереднє 4.1), якої LLM не мав, і вердикт перевернувся з
    нічиєї (0.0714 проти 0.0714) на "LLM гірший на 14.3%". MAE
    порівнюються честно лише тоді, коли набір точок ОДНАКОВИЙ для всіх
    трьох моделей."""
    chronological = list(observations_desc[::-1])
    values = [float(o["value"]) for o in chronological]

    first_index = max(min_history, len(values) - points)

    llm_errors: list[float] = []
    naive_errors: list[float] = []
    trend_errors: list[float] = []
    n_skipped = 0

    for i in range(first_index, len(values)):
        history_rows = chronological[:i]
        history_values = values[:i]
        actual = values[i]

        llm_pred = forecast_fn(history_rows)
        if llm_pred is None:
            # Точка не входить НІ в LLM-MAE, НІ в базові лінії —
            # інакше набори точок розійшлись би (див. докстрінг).
            n_skipped += 1
            logger.warning(
                "%s @ %s: прогнозу немає — точка пропущена (і для базових ліній теж)",
                metric_id, chronological[i]["observed_at"],
            )
            continue

        llm_errors.append(abs(actual - llm_pred))
        logger.info(
            "%s @ %s: факт=%.6g LLM=%.6g (|похибка|=%.6g)",
            metric_id, chronological[i]["observed_at"], actual, llm_pred,
            abs(actual - llm_pred),
        )

        naive_pred = naive_forecast(history_values)
        if naive_pred is not None:
            naive_errors.append(abs(actual - naive_pred))
        trend_pred = linear_trend_forecast(history_values)
        if trend_pred is not None:
            trend_errors.append(abs(actual - trend_pred))

    return {
        "metric_id": metric_id,
        "n_points": len(llm_errors),
        "n_skipped": n_skipped,
        "llm_mae": _mae(llm_errors),
        "naive_mae": _mae(naive_errors),
        "trend_mae": _mae(trend_errors),
    }


def make_llm_forecast_fn(conn, metric_id: str, api_key: str) -> Callable[[list[dict]], Optional[float]]:
    """forecast_fn для backtest_llm_metric(): той САМИЙ промпт і той
    самий гейт правдоподібності, що в бойовому forecast_metric.py —
    інакше backtest міряв би не те, що працює в продакшені.

    Кожен виклик пишеться в llm_call_log із purpose
    'metric_forecast_backtest' (rule 5, CLAUDE.md) — окремо від
    бойового 'metric_forecast', щоб backtest-прогони не змішувались з
    реальними при розборі постфактум."""

    def forecast_fn(history_rows: list[dict]) -> Optional[float]:
        prompt = build_prompt(metric_id, describe_metric(metric_id), history_rows)
        try:
            raw_content = call_llm(prompt, SYSTEM_PROMPT, api_key)
        except requests.exceptions.RequestException:
            logger.exception("%s: мережева помилка виклику LLM", metric_id)
            return None

        log_llm_call(
            conn,
            provider=resolve_provider(),
            purpose="metric_forecast_backtest",
            prompt=prompt,
            response=raw_content,
            source_ref=f"{metric_id}:{history_rows[-1]['observed_at']}",
        )

        try:
            result = parse_forecast_response(raw_content)
        except SynthesisResponseError:
            logger.exception("%s: некоректна відповідь LLM", metric_id)
            return None

        plausible, reason = is_plausible(
            [float(r["value"]) for r in history_rows], result.forecast_value
        )
        if not plausible:
            logger.error("%s: прогноз відкинуто гейтом — %s", metric_id, reason)
            return None
        return result.forecast_value

    return forecast_fn


def format_verdict(result: dict) -> str:
    """Людський вердикт за критерієм analysis/CLAUDE.md (точніша за
    naive), з чесною поправкою на малу вибірку."""
    llm_mae, naive_mae = result["llm_mae"], result["naive_mae"]
    if llm_mae is None or naive_mae is None:
        return "вердикту немає — жодної перевіреної точки"

    if naive_mae == 0:
        # Naive без жодної похибки (абсолютно плоска серія) — відносна
        # різниця не визначена, тож віддаємо абсолютні числа.
        return (
            "naive безпомилковий на цих точках (серія не змінювалась) — "
            f"LLM MAE {llm_mae:.6g}, порівнювати у відсотках нема з чим"
        )

    diff_pct = (naive_mae - llm_mae) / naive_mae * 100
    # Поріг нічиєї: < 0.05% різниці округлилось би до "0.0%", і вивід
    # "LLM гірший на 0.0%" виглядав би як збій, а не як рівність
    # (живий кейс `unemployment_rate` 2026-10-04 — рівно однакові MAE).
    if abs(diff_pct) < 0.05:
        return "нічия — LLM і naive однаково точні на цих точках"
    if diff_pct > 0:
        return f"LLM точніший за naive на {diff_pct:.1f}%"
    return f"naive кращий — LLM гірший на {abs(diff_pct):.1f}%"


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metric", required=True)
    parser.add_argument(
        "--points", type=int, default=DEFAULT_POINTS,
        help=f"скільки останніх точок перевірити (= стільки викликів LLM, дефолт {DEFAULT_POINTS})",
    )
    parser.add_argument("--min-history", type=int, default=DEFAULT_MIN_HISTORY)
    parser.add_argument(
        "--limit", type=int, default=200, help="скільки останніх спостережень тягнути з БД"
    )
    args = parser.parse_args()

    api_key = require_api_key()

    try:
        source = resolve_source(args.metric)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    conn = get_connection()
    try:
        observations = fetch_recent(conn, source, args.metric, limit=args.limit)
        if len(observations) <= args.min_history:
            logger.error(
                "%s: замало історії (%d, потрібно > %d) — backtest неможливий",
                args.metric, len(observations), args.min_history,
            )
            sys.exit(1)

        result = backtest_llm_metric(
            args.metric,
            observations,
            make_llm_forecast_fn(conn, args.metric, api_key),
            points=args.points,
            min_history=args.min_history,
        )
    finally:
        conn.close()

    if result["n_points"] == 0:
        logger.error(
            "%s: жодної точки не вдалось перевірити (пропущено %d) — результату немає",
            args.metric, result["n_skipped"],
        )
        sys.exit(1)

    # Провайдер у виводі ОБОВ'ЯЗКОВО (2026-10-04, питання користувача):
    # числа в колонці LLM специфічні для конкретної моделі, і при
    # переході на іншу (планується при більшому бюджеті) порівнювати
    # можна лише знаючи, чим міряно. naive/лінійний тренд від
    # провайдера не залежать — чиста арифметика на самому ряді.
    logger.info(
        "%s [provider=%s]: %d точок перевірено (пропущено %d), MAE LLM=%.6g, "
        "naive=%.6g, лінійний тренд=%s — %s",
        result["metric_id"], resolve_provider(), result["n_points"], result["n_skipped"],
        result["llm_mae"], result["naive_mae"],
        f"{result['trend_mae']:.6g}" if result["trend_mae"] is not None else "n/a",
        format_verdict(result),
    )


if __name__ == "__main__":
    main()
