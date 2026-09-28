"""
SHORT/WATCH-скринінг — окремий алгоритм від LONG (пряма вимога
користувача, 2026-09-27) — виснаження/розворот ПІСЛЯ пампу, не просто
"ціна падає". Той самий стиль чистої функції рішення, що long_screen.py
— приймає вже пораховані індикатори (aggregate_sources.py, forecasting/,
crypto_screening/indicators.py), не рахує їх сама.

**Критично для правильного розуміння (пряма вимога користувача,
2026-09-27, докладніше docs/decisions.md):** критично негативний
funding ПІСЛЯ пампу — це НЕ підтвердження шорту, а сигнал, що вже
багато шортистів У ПОЗИЦІЇ (натовп), яких може "винести" (short
squeeze) — відкривати НОВИЙ шорт проти вже перевантаженого натовпу
шортистів небезпечно, а не безпечно. Такі монети НЕ відсіюються
зовсім — переходять у окрему категорію WATCH (цікаві самі по собі,
велика вірогідність активності маркет-мейкера/маніпуляції на тлі
скупчення шортистів — підхід до аналізу інший, не автоматичний
напрямок сигналу).

**Заборонені формулювання (analysis/CLAUDE.md, без винятку):**
результат — "ведмежий нахил" (direction="down") для category="short",
"спостереження" для category="watch" (без напрямку) — НІКОЛИ "шорти
це"/"входь у шорт". `reasons` — для аудиту, не інструкція.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

# Пороги — довільний старт, калібрувати на живих даних (той самий
# чесний підхід, що аналогічні пороги в analysis/screening/).
PUMP_THRESHOLD_PCT = 30.0
# -2% за період — критичний поріг небезпеки (пряма вказівка користувача, 2026-09-27).
CRITICAL_NEGATIVE_FUNDING = Decimal("-0.02")
RSI_OVERBOUGHT = 70.0
MIN_VOLUME_SPIKE_PCT = 20.0


@dataclass
class ShortWatchSignal:
    symbol: str
    category: str  # "short" | "watch" | "none"
    direction: Optional[str]  # "down" лише для "short", інакше None
    reasons: list[str] = field(default_factory=list)


def screen_short_or_watch(
    symbol: str,
    pump_pct: Optional[float],
    oi_change_pct_after_pump: Optional[float],
    volume_spike_pct: Optional[float],
    rsi_value: Optional[float],
    funding_rate: Optional[Decimal],
) -> ShortWatchSignal:
    if pump_pct is None or pump_pct < PUMP_THRESHOLD_PCT:
        return ShortWatchSignal(
            symbol=symbol, category="none", direction=None,
            reasons=["немає пампу за вікном — сетап розвороту не застосовний"],
        )

    # Критичний ризик-гейт ПЕРШИМ, ще до перевірки решти критеріїв —
    # користувач, 2026-09-27: така монета НЕ фільтрується геть, а йде
    # в спостереження, незалежно від того, чи є інші ознаки виснаження.
    if funding_rate is not None and funding_rate <= CRITICAL_NEGATIVE_FUNDING:
        return ShortWatchSignal(
            symbol=symbol, category="watch", direction=None,
            reasons=[
                f"памп {pump_pct:.1f}% + критично негативний funding {funding_rate} "
                "— натовп шортистів уже в позиції, ризик short squeeze для нового шорту"
            ],
        )

    reasons = []
    if oi_change_pct_after_pump is None or oi_change_pct_after_pump >= 0:
        reasons.append("Open Interest не падає після пампу — леверидж-лонги ще не закриваються")
    if volume_spike_pct is None or volume_spike_pct < MIN_VOLUME_SPIKE_PCT:
        reasons.append("немає сплеску обсягу — рух не підтверджений")
    if rsi_value is None or rsi_value < RSI_OVERBOUGHT:
        reasons.append(f"RSI не перегрітий (< {RSI_OVERBOUGHT})")

    if reasons:
        return ShortWatchSignal(symbol=symbol, category="none", direction=None, reasons=reasons)

    return ShortWatchSignal(
        symbol=symbol,
        category="short",
        direction="down",
        reasons=[
            f"памп {pump_pct:.1f}% + OI падає {oi_change_pct_after_pump:.1f}% "
            "+ сплеск обсягу + RSI перегрітий — ознаки виснаження руху"
        ],
    )
