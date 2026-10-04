"""
LLM-прогноз наступного значення одного макропоказника — ЧИСТА частина
(промпт + розбір відповіді + перевірка правдоподібності), без SQL і без
мережі, тестується на голих списках чисел (той самий стиль, що
trend.py).

## Чому LLM, а не лінійна регресія (зміна напрямку, 2026-09-28)

Рішення користувача (docs/decisions.md, "Повний новий спек"): прогноз
має формувати ШІ на основі зібраних даних, а НЕ Python-модель
(`trend.py:linear_trend_forecast`). Це свідомий виняток із
analysis/CLAUDE.md "не використовуйте LLM для того, що можна порахувати
звичайною формулою" — власне рішення користувача саме для
прогнозування, не порушення правила.

`trend.py` при цьому НЕ видаляється: `naive_forecast()` лишається
базовою лінією, проти якої міряється будь-яка модель (analysis/CLAUDE.md
"Тестування прогнозних моделей"), а `linear_trend_forecast()` — другою
точкою порівняння в `backtest_llm.py`. Видалити їх означало б втратити
можливість сказати, чи LLM узагалі кращий за "нічого не змінилось".

## Що СВІДОМО не йде в промпт: ринкове очікування

`release_log.expected_value` (прогноз ForexFactory на наступний реліз)
у промпт НЕ передається, хоча технічно доступний. Дві причини:
1. Наш прогноз має бути ТРЕТЬОЮ незалежною точкою зору поруч із фактом
   і ринковим консенсусом (PLAN.md, Фаза 2) — заанкорений на консенсус
   прогноз такої цінності не має, він лише перекаже консенсус.
2. Backtest (`backtest_llm.py`) рахується на історії, де ринкового
   очікування на той момент у БД немає — промпт, що залежить від нього,
   був би неперевірюваним.
Порівняння "наш прогноз vs ринковий" робиться ПІЗНІШЕ, при видачі
(`reporting/forecast_notify.py`), де обидва числа вже відомі.

## Перевірка правдоподібності (is_plausible)

LLM легко плутає одиниці показника (рівень індексу CPI ~320 проти
річної зміни ~3.2%) або видає число іншого порядку. Такий прогноз
гірший за відсутній: він тихо потрапив би в Telegram як готовий
висновок. Тому ЧИСЛО від LLM проходить детермінований гейт перед
збереженням — той самий принцип "контроль коректності є властивістю
системи, не ручною роботою в сесії" (критичне правило 7, CLAUDE.md).
"""

import logging
from dataclasses import dataclass
from typing import Optional

from llm_common import (
    DIRECTIONS,
    SynthesisResponseError,
    parse_confidence,
    parse_json_object,
)

logger = logging.getLogger(__name__)

# Скільки найбільших історичних кроків (|Δ| між сусідніми точками)
# дозволено прогнозу відійти від останнього відомого значення, перш ніж
# він вважається неправдоподібним. 3 — свідомо щедро: мета гейта —
# ловити помилку ОДИНИЦЬ/порядку (320 проти 3.2), не "надто смілий, але
# осмислений" прогноз. Калібрування — після накопичення живих відхилень.
PLAUSIBILITY_FACTOR = 3.0

# Мінімум точок історії, щоб гейт мав на чому працювати: з 2 точок є
# лише один крок, і він же — міра "нормального" кроку, що робить
# перевірку безсенсовою (будь-який прогноз у межах 3 кроків пройде).
PLAUSIBILITY_MIN_HISTORY = 4

# ОБОВ'ЯЗКОВІ поля відповіді. `reasoning` свідомо НЕ тут (2026-10-04,
# живий кейс `unemployment_rate`): DeepSeek віддав коректний прогноз
# (forecast_value/direction/confidence/summary), але без `reasoning` —
# і вся точка backtest була втрачена через відсутнє поле для АУДИТУ.
# Аудит при цьому не страдає: повна сира відповідь однаково лежить у
# `llm_call_log` (rule 5, CLAUDE.md), тобто `reasoning` — зручність
# читання, а не єдине джерело обґрунтування. Відкидати робочий прогноз
# через нього — строгість не на користь справі.
FORECAST_FIELDS = ("forecast_value", "direction", "confidence", "summary")

SYSTEM_PROMPT = (
    "Ти макро-аналітик. Тобі дають історію одного макроекономічного "
    "показника — впорядкований за часом список (дата: значення), у тих "
    "самих одиницях, у яких показник публікує офіційне джерело."
    "\n\n"
    "Твоя задача — спрогнозувати, яким буде НАСТУПНЕ значення цього "
    "показника (наступний період публікації), і пояснити чому."
    "\n\n"
    "КРИТИЧНО про одиниці: прогноз має бути в ТИХ САМИХ одиницях і "
    "того самого порядку величини, що значення в наданій історії. Якщо "
    "історія — рівень індексу (напр. 322.1), прогнозуй рівень індексу, "
    "а НЕ річну зміну у відсотках. Якщо історія — відсоток (напр. 4.2), "
    "прогнозуй відсоток. Число іншого порядку буде відкинуто як "
    "помилкове."
    "\n\n"
    "Опирайся на те, що видно в самих даних: напрямок і крутизна "
    "останнього тренду, типовий розмір кроку між періодами, сезонність "
    "(якщо проглядається), розвороти, чи рух сповільнюється. Якщо дані "
    "не дають підстав для зміни — чесно прогнозуй значення, близьке до "
    "останнього, і скажи це в обґрунтуванні; вигадана динаміка гірша "
    "за визнану невизначеність."
    "\n\n"
    "НІКОЛИ не давай торгових рекомендацій ('купити'/'продати'/"
    "'входити в позицію') — тільки опис показника й очікуваної "
    "динаміки. Відповідай ЛИШЕ JSON-об'єктом з полями: forecast_value "
    "(ЧИСЛО — прогноз наступного значення, у тих самих одиницях, що "
    "історія), direction (одне з: up, down, neutral, unclear — куди "
    "показник рухається відносно останнього відомого значення), "
    "confidence (число від 0 до 1 — наскільки впевнений прогноз), "
    "summary (1-2 речення: яке значення очікується і чому), reasoning "
    "(коротке обґрунтування для аудиту: на яку саме динаміку в даних ти "
    "спирався)."
)


@dataclass
class ForecastResult:
    """Вихід LLM-прогнозу. Своя форма (додає `forecast_value`), тому
    власний клас і власний парсер тут, а не
    llm_common.parse_synthesis_response() — той самий принцип, що
    expectations/synthesize.py:ExpectationSynthesisResult."""

    forecast_value: float
    direction: str
    confidence: float
    summary: str
    reasoning: str


def parse_forecast_response(raw_content: str) -> ForecastResult:
    data = parse_json_object(raw_content, error_class=SynthesisResponseError)

    missing = [f for f in FORECAST_FIELDS if f not in data]
    if missing:
        raise SynthesisResponseError(f"У відповіді LLM бракує полів {missing}: {data!r}")

    try:
        forecast_value = float(data["forecast_value"])
    except (TypeError, ValueError) as e:
        raise SynthesisResponseError(
            f"forecast_value не число: {data['forecast_value']!r}"
        ) from e

    direction = data["direction"]
    if direction not in DIRECTIONS:
        raise SynthesisResponseError(f"Неочікуване значення direction: {direction!r}")

    reasoning = data.get("reasoning")
    if not reasoning:
        # Не помилка (див. FORECAST_FIELDS вище) — але лог потрібен,
        # щоб систематичне зникнення поля було видно, а не вгадувалось.
        logger.warning(
            "reasoning відсутнє у відповіді LLM — прогноз приймається, "
            "обґрунтування беремо з summary (повна відповідь — у llm_call_log)"
        )
        reasoning = data["summary"]

    return ForecastResult(
        forecast_value=forecast_value,
        direction=direction,
        confidence=parse_confidence(data["confidence"], error_class=SynthesisResponseError),
        summary=data["summary"],
        reasoning=reasoning,
    )


def is_plausible(values: list[float], forecast_value: float) -> tuple[bool, Optional[str]]:
    """(чи правдоподібний, причина відхилення). `values` — ХРОНОЛОГІЧНО
    (найстаріше перше), той самий порядок, що trend.py.

    Міра "нормального" кроку — НАЙБІЛЬШИЙ історичний |Δ| між сусідніми
    точками, а не середній: середній крок гладкої серії (CPI) близький
    до нуля, і будь-який осмислений прогноз відхилявся б від нього на
    багато "кроків". Максимум — найщедріша розумна межа, яку видно
    прямо в даних.

    Серія без жодного руху (усі кроки 0) гейт не проходить ніхто, крім
    точного повтору останнього значення — тому такий випадок свідомо
    пропускається (повертає True): це не помилка одиниць, а вироджена
    історія, і краще зберегти прогноз, ніж відкинути все."""
    if len(values) < PLAUSIBILITY_MIN_HISTORY:
        return True, None

    steps = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
    max_step = max(steps)
    if max_step == 0:
        return True, None

    last = values[-1]
    deviation = abs(forecast_value - last)
    limit = PLAUSIBILITY_FACTOR * max_step
    if deviation > limit:
        return False, (
            f"прогноз {forecast_value:.6g} відходить від останнього відомого "
            f"{last:.6g} на {deviation:.6g} — більше за {PLAUSIBILITY_FACTOR}× "
            f"найбільшого історичного кроку ({max_step:.6g}); схоже на помилку "
            f"одиниць/порядку, не на прогноз"
        )
    return True, None


def build_prompt(metric_id: str, label: str, observations_chronological: list[dict]) -> str:
    """`observations_chronological` — найстаріше перше (як trend.py), з
    ключами observed_at/value; викликач відповідає за розворот
    fetch_recent()."""
    lines = [
        f"Показник: {label} (metric_id={metric_id})",
        f"Кількість точок історії: {len(observations_chronological)}",
        "",
        "Історія (від найстарішого до найновішого):",
    ]
    for obs in observations_chronological:
        lines.append(f"{obs['observed_at']}: {float(obs['value']):.6g}")
    lines.append("")
    lines.append(
        "Спрогнозуй наступне значення цього показника (наступний період "
        "публікації) у тих самих одиницях."
    )
    return "\n".join(lines)


# metric_id → опис для ПРОМПТА: що це за серія, в яких одиницях і з
# якою частотою публікується (docs/metrics-catalog.md). Свідомо окремо
# від reporting/telegram_notify.py:METRIC_LABELS — там підпис для
# ЛЮДИНИ в Telegram (короткий), тут контекст для МОДЕЛІ (одиниці й
# частота, без яких LLM плутає рівень індексу з річною зміною, і без
# яких "наступний період" неоднозначний: тиждень/місяць/квартал).
# analysis/ і reporting/ лишаються незалежними (жодного імпорту між
# ними) — той самий принцип, що reporting/CLAUDE.md.
METRIC_DESCRIPTIONS = {
    "cpi": "CPI США (CPIAUCSL) — РІВЕНЬ індексу споживчих цін, публікується щомісяця",
    "core_cpi": "Core CPI США (CPILFESL, без їжі/енергії) — РІВЕНЬ індексу, щомісяця",
    "pce_price_index": "PCE Price Index США (PCEPI, орієнтир ФРС) — РІВЕНЬ індексу, щомісяця",
    "fed_funds_rate": "Effective Fed Funds Rate (DFF) — ставка у відсотках, щодня",
    "treasury_10y": "Дохідність 10-річних US Treasuries (DGS10) — відсотки, щодня",
    "treasury_2y": "Дохідність 2-річних US Treasuries (DGS2) — відсотки, щодня",
    "unemployment_rate": "Рівень безробіття США (UNRATE) — відсотки, щомісяця",
    "nonfarm_payrolls": "Non-Farm Payrolls США (PAYEMS) — ЗАГАЛЬНА зайнятість у тисячах осіб (рівень, не приріст), щомісяця",
    "initial_jobless_claims": "Initial Jobless Claims США (ICSA) — кількість первинних заявок на допомогу, щотижня",
    "real_gdp": "Real GDP США (GDPC1) — РІВЕНЬ у млрд доларів 2017 року (chained), щокварталу",
    "retail_sales": "Retail Sales США (RSAFS) — РІВЕНЬ роздрібних продажів у млн доларів, щомісяця",
    "housing_starts": "Housing Starts США (HOUST) — початки будівництва, тисяч одиниць (SAAR), щомісяця",
    "mortgage_rate_30y": "30-річна фіксована ставка по іпотеці США (MORTGAGE30US) — відсотки, щотижня",
    "usdjpy_fx_rate": "Курс USD/JPY (DEXJPUS, Fed H.10) — єн за долар, щодня",
    "eurozone_hicp": "HICP єврозони — РІЧНА зміна у відсотках (annual rate of change), щомісяця",
    "eurozone_deposit_rate": "Deposit Facility Rate ЄЦБ — ставка у відсотках, щодня",
    "eurozone_unemployment_rate": "Рівень безробіття єврозони — відсотки, щомісяця",
    "japan_policy_rate": "Uncollateralized O/N Call Rate (політична ставка Банку Японії) — відсотки",
    "japan_cpi": "CPI Японії (e-Stat, база 2025=100) — РІВЕНЬ індексу, щомісяця",
}


def describe_metric(metric_id: str) -> str:
    """Опис показника для промпта. Невідомий metric_id — віддаємо сам
    id (прогноз усе одно можливий: історія в промпті несе одиниці
    неявно), не падаємо: перелік показників проєкту росте, і новий
    показник без опису має працювати гірше, а не ніяк."""
    return METRIC_DESCRIPTIONS.get(metric_id, metric_id)
