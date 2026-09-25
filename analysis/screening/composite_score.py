"""Composite score: фінальне ранжування тикерів, що пройшли Tier A/B/C.

Формула (docs/screening-criteria.md):
    score = 0.35 * percentile(revenue_growth)
          + 0.30 * percentile(eps_growth)
          + 0.20 * percentile(-P/E)
          + 0.15 * percentile(avg_dollar_volume)

Це НЕ ще один hard-фільтр (як Tier A/B/C) -- composite score нічого не
відсіює, він тільки ранжує список тикерів, що вже пройшли всі три рівні
скринінгу, від найпривабливішого до найменш привабливого. Скільки з
верху списку брати (5, 10, 20) -- рішення користувача, а не жорсткий
поріг у коді, тому run_composite_score() за замовчуванням повертає
ПОВНИЙ ранжований список; --top лише обрізає ВИВІД у __main__.

Percentile тут -- percentile RANK всередині самого набору тикерів, що
пройшли Tier C (не percentile відносно всього S&P 500): наприклад,
якщо в списку 16 тикерів і в тикера X eps_growth вище, ніж у 12 з 15
інших, його percentile(eps_growth) = 12/15 ≈ 0.80. Це узгоджено з
задумом критеріїв: порівнюємо тільки вже відфільтрованих кандидатів
між собою, а не з усім ринком.

-P/E: нижчий P/E -- краще (дешевша оцінка відносно прибутку), тому
percentile рахується від'ємного P/E (percentile_rank(-pe)), а не
від самого P/E.
"""

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

_ANALYSIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ANALYSIS_DIR)
sys.path.insert(0, os.path.join(_ANALYSIS_DIR, "..", "data-ingestion"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Вагові коефіцієнти формули (docs/screening-criteria.md)
WEIGHT_REVENUE_GROWTH = Decimal("0.35")
WEIGHT_EPS_GROWTH = Decimal("0.30")
WEIGHT_NEG_PE = Decimal("0.20")
WEIGHT_AVG_DOLLAR_VOLUME = Decimal("0.15")


@dataclass
class CompositeResult:
    ticker: str
    score: Decimal
    revenue_growth: Decimal
    eps_growth: Decimal
    pe: Decimal
    avg_dollar_volume: Decimal
    revenue_growth_pct: Decimal
    eps_growth_pct: Decimal
    neg_pe_pct: Decimal
    avg_dollar_volume_pct: Decimal


def percentile_ranks(values: list[Decimal]) -> list[Decimal]:
    """Percentile rank (0..1) кожного значення всередині власного списку.

    Метод середнього рангу (average rank) для коректної обробки
    однакових значень (tie): rank(x) = (к-сть менших) + (к-сть рівних - 1) / 2,
    percentile = rank / (n - 1).

    n <= 1 -> усі отримують 0.5 (нема з чим порівнювати).
    """
    n = len(values)
    if n <= 1:
        return [Decimal("0.5") for _ in values]

    result = []
    for v in values:
        less = sum(1 for x in values if x < v)
        equal = sum(1 for x in values if x == v)
        rank = Decimal(less) + (Decimal(equal) - 1) / 2
        result.append(rank / (n - 1))
    return result


def run_composite_score(
    tier_a_results=None, tier_b_results=None, tier_c_results=None
) -> list[CompositeResult]:
    from screening.tier_a import run_tier_a
    from screening.tier_b import run_tier_b
    from screening.tier_c import run_tier_c

    if tier_a_results is None:
        tier_a_results = run_tier_a()
    if tier_b_results is None:
        tier_b_results = run_tier_b()
    if tier_c_results is None:
        tier_c_results = run_tier_c(tier_a_results=tier_a_results, tier_b_results=tier_b_results)

    tier_a_by_ticker = {r.ticker: r for r in tier_a_results}
    tier_b_by_ticker = {r.ticker: r for r in tier_b_results}

    passed_c = [r for r in tier_c_results if r.passed]

    rows = []
    skipped = []
    for c in passed_c:
        a = tier_a_by_ticker.get(c.ticker)
        b = tier_b_by_ticker.get(c.ticker)
        if a is None or b is None:
            skipped.append(c.ticker)
            continue

        # TierAResult.avg_dollar_volume і TierBResult.revenue_yoy/eps_yoy --
        # звичайні (не Optional) поля, завжди присутні. TierCResult.pe --
        # Optional[Decimal] типово, але для passed=True тикера завжди
        # обчислений (інакше він би не пройшов поріг MIN_PE..MAX_PE) --
        # перевірка залишена як страховка на випадок зміни tier_c.py.
        revenue_growth = b.revenue_yoy
        eps_growth = b.eps_yoy
        avg_dollar_volume = a.avg_dollar_volume
        pe = c.pe

        if pe is None:
            logger.warning("%s: pe відсутній у пройденого Tier C результату -- пропускаю", c.ticker)
            skipped.append(c.ticker)
            continue

        rows.append(
            {
                "ticker": c.ticker,
                "revenue_growth": revenue_growth,
                "eps_growth": eps_growth,
                "pe": pe,
                "avg_dollar_volume": avg_dollar_volume,
            }
        )

    if skipped:
        logger.warning("Пропущено через відсутні дані: %s", skipped)

    if not rows:
        return []

    revenue_pcts = percentile_ranks([r["revenue_growth"] for r in rows])
    eps_pcts = percentile_ranks([r["eps_growth"] for r in rows])
    neg_pe_pcts = percentile_ranks([-r["pe"] for r in rows])
    volume_pcts = percentile_ranks([r["avg_dollar_volume"] for r in rows])

    results = []
    for row, rev_pct, eps_pct, negpe_pct, vol_pct in zip(
        rows, revenue_pcts, eps_pcts, neg_pe_pcts, volume_pcts
    ):
        score = (
            WEIGHT_REVENUE_GROWTH * rev_pct
            + WEIGHT_EPS_GROWTH * eps_pct
            + WEIGHT_NEG_PE * negpe_pct
            + WEIGHT_AVG_DOLLAR_VOLUME * vol_pct
        )
        results.append(
            CompositeResult(
                ticker=row["ticker"],
                score=score,
                revenue_growth=row["revenue_growth"],
                eps_growth=row["eps_growth"],
                pe=row["pe"],
                avg_dollar_volume=row["avg_dollar_volume"],
                revenue_growth_pct=rev_pct,
                eps_growth_pct=eps_pct,
                neg_pe_pct=negpe_pct,
                avg_dollar_volume_pct=vol_pct,
            )
        )

    results.sort(key=lambda r: r.score, reverse=True)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Composite score ранжування кандидатів")
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        help="Показати тільки топ-N (за замовчуванням -- усі, що пройшли Tier C)",
    )
    args = parser.parse_args()

    all_results = run_composite_score()

    logger.info("Ранжовано %d тикерів (усі, що пройшли Tier A -> B -> C)", len(all_results))

    to_show = all_results[: args.top] if args.top else all_results

    print(f"{'#':<4}{'Ticker':<8}{'Score':>8}{'RevG%':>8}{'EpsG%':>8}{'P/E':>8}{'AvgVol$M':>10}")
    for i, r in enumerate(to_show, start=1):
        print(
            f"{i:<4}{r.ticker:<8}{float(r.score):>8.3f}"
            f"{float(r.revenue_growth) * 100:>7.1f}%"
            f"{float(r.eps_growth) * 100:>7.1f}%"
            f"{float(r.pe):>8.1f}"
            f"{float(r.avg_dollar_volume) / 1_000_000:>10.1f}"
        )
