"""
Tier A — спільний фільтр допуску для крипто-скринінгу лонг/шорт/
спостереження (крок 4, docs/decisions.md 2026-09-27). Той самий
принцип, що analysis/screening/tier_a.py (акції) — ліквідність-гейт
ПЕРЕД дорожчою логікою (LONG/SHORT-алгоритми), не судження про напрямок
сигналу. Чиста функція (rule 1) — приймає вже агреговані дані
(aggregate_sources.py), не звертається до БД/API.

Критерії (значення — початкові орієнтири, підлягають калібруванню на
живих прогонах, той самий чесний підхід, що аналогічні пороги в
analysis/screening/):
- `MIN_QUOTE_VOLUME_24H` — мін. агрегований $-обсяг за добу (та сама
  планка, що Tier A акцій: $10 млн/добу).
- `MIN_OPEN_INTEREST_USD` — мін. агрегований Open Interest.
- `MIN_EXCHANGE_COUNT` — присутність щонайменше на 2 з 3 бірж —
  безкоштовний proxy "легітимності" (не фінансова оцінка, лише факт
  лістингу на кількох незалежних майданчиках одночасно).
- `MIN_LISTING_AGE_DAYS` — мін. вік лістингу (найстаріший з `onboard_date`
  серед бірж, де символ присутній) — відсіює щойно-лістовані/
  маніпульовані контракти.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

MIN_QUOTE_VOLUME_24H = Decimal("10000000")   # $10 млн/добу
MIN_OPEN_INTEREST_USD = Decimal("5000000")   # $5 млн
MIN_EXCHANGE_COUNT = 2
MIN_LISTING_AGE_DAYS = 30


@dataclass
class TierAResult:
    symbol: str
    eligible: bool
    reasons: list[str] = field(default_factory=list)  # порожньо, якщо eligible


def check_tier_a(
    symbol: str,
    aggregated: dict,
    oldest_onboard_date: Optional[date],
    today: date,
) -> TierAResult:
    reasons = []

    if aggregated["quote_volume_24h"] < MIN_QUOTE_VOLUME_24H:
        reasons.append(
            f"обсяг ${aggregated['quote_volume_24h']:,.0f} < ${MIN_QUOTE_VOLUME_24H:,.0f}"
        )
    if aggregated["open_interest_usd"] < MIN_OPEN_INTEREST_USD:
        reasons.append(
            f"OI ${aggregated['open_interest_usd']:,.0f} < ${MIN_OPEN_INTEREST_USD:,.0f}"
        )
    if aggregated["exchange_count"] < MIN_EXCHANGE_COUNT:
        reasons.append(
            f"лише на {aggregated['exchange_count']} з 3 бірж (< {MIN_EXCHANGE_COUNT})"
        )
    if oldest_onboard_date is None:
        reasons.append("невідома дата лістингу")
    else:
        age_days = (today - oldest_onboard_date).days
        if age_days < MIN_LISTING_AGE_DAYS:
            reasons.append(f"вік лістингу {age_days}д < {MIN_LISTING_AGE_DAYS}д")

    return TierAResult(symbol=symbol, eligible=not reasons, reasons=reasons)
