"""
ЄДИНИЙ конфіг агента (`config.py` у корені) — одне джерело істини
для всіх порогів (рішення користувача 2026-10-04: "конфіг один на весь
агент"; до того було по конфігу на модуль).

Тести стежать саме за цим: щоб модулі брали значення з `config.py`, а
не мали власних копій. Інакше правка в продакшені тихо не подіяла б —
рівно той клас проблеми, через який конфіг і попросили.
"""

import re
from pathlib import Path

import pytest

import config

_ANALYSIS_DIR = Path(__file__).resolve().parent.parent

# Назва константи → модулі, які її СПОЖИВАЮТЬ (і не мають визначати).
CONSUMERS = {
    "ANOMALY_SIGMA_MULTIPLIER": ["news_analysis/prices.py"],
    "ANOMALY_MIN_HISTORY": ["news_analysis/prices.py"],
    "ANOMALY_HISTORY_LOOKBACK": ["news_analysis/prices.py"],
    "SIMILARITY_THRESHOLD": ["news_analysis/aggregate.py"],
    "CROSS_RUN_SIMILARITY_THRESHOLD": ["news_analysis/_consolidated_db.py"],
    "MIN_NORMALIZED_LENGTH_FOR_MATCHING": ["news_analysis/aggregate.py"],
    # Скринінг акцій — перенесений 2026-10-05 (при першому зливанні
    # лишився в модулях, тобто вимога "один конфіг" була виконана
    # наполовину).
    "MIN_PRICE": ["screening/tier_a.py"],
    "MIN_MARKET_CAP": ["screening/tier_a.py"],
    "MIN_AVG_DOLLAR_VOLUME": ["screening/tier_a.py"],
    "MIN_REVENUE_YOY": ["screening/tier_b.py"],
    "MIN_EPS_YOY": ["screening/tier_b.py"],
    "MAX_LIABILITIES_TO_ASSETS": ["screening/tier_b.py"],
    "MIN_PE": ["screening/tier_c.py"],
    "MAX_PE": ["screening/tier_c.py"],
    "MAX_PEG": ["screening/tier_c.py"],
    "WEIGHT_REVENUE_GROWTH": ["screening/composite_score.py"],
    # Чинники фундаментального аналізу (2026-10-04).
    "ASSET_FACTORS": ["fundamental/factors.py"],
    "ASSET_FACTOR_GAPS": ["fundamental/factors.py"],
    "DEFAULT_ASSET_FACTORS": ["fundamental/factors.py"],
}


@pytest.mark.parametrize("name", sorted(CONSUMERS))
def test_config_defines_every_tunable(name):
    assert hasattr(config, name), f"{name} зник із config.py"


@pytest.mark.parametrize("name,modules", sorted(CONSUMERS.items()))
def test_consumers_do_not_hardcode_value(name, modules):
    """Присвоєння ЛІТЕРАЛУ в модулі-споживачі означало б другу копію
    значення — і правка в config.py не подіяла б."""
    literal = re.compile(rf"^{name}\s*=\s*[0-9.]+\s*$", re.MULTILINE)
    for module in modules:
        text = (_ANALYSIS_DIR / module).read_text()
        assert not literal.search(text), (
            f"{module}: {name} присвоєно літералом — має братись із config.py"
        )


def test_prices_uses_config_values():
    """Не лише імпорт, а фактична рівність — щоб перейменування чи
    локальний перекрив не пройшли непоміченими."""
    from news_analysis import prices

    assert prices.ANOMALY_SIGMA_MULTIPLIER == config.ANOMALY_SIGMA_MULTIPLIER
    assert prices.ANOMALY_MIN_HISTORY == config.ANOMALY_MIN_HISTORY
    assert prices.ANOMALY_HISTORY_LOOKBACK == config.ANOMALY_HISTORY_LOOKBACK


def test_aggregate_uses_config_values():
    from news_analysis import aggregate

    assert aggregate.DEFAULT_SIMILARITY_THRESHOLD == config.SIMILARITY_THRESHOLD
    assert (
        aggregate.MIN_NORMALIZED_LENGTH_FOR_MATCHING
        == config.MIN_NORMALIZED_LENGTH_FOR_MATCHING
    )


def test_sigma_multiplier_is_sane():
    """0 зробив би аномальним будь-який рух, відʼємне — безглузде."""
    assert config.ANOMALY_SIGMA_MULTIPLIER > 0


def test_similarity_thresholds_in_unit_range():
    for value in (config.SIMILARITY_THRESHOLD, config.CROSS_RUN_SIMILARITY_THRESHOLD):
        assert 0 < value <= 1


def test_min_history_above_one():
    """stdev з однієї точки не існує — порог нижче 2 зламав би
    розрахунок волатильності."""
    assert config.ANOMALY_MIN_HISTORY >= 2


def test_lookback_not_smaller_than_min_history():
    """Інакше тягнули б менше точок, ніж вимагаємо для розрахунку."""
    assert config.ANOMALY_HISTORY_LOOKBACK >= config.ANOMALY_MIN_HISTORY


def test_composite_weights_sum_to_one():
    """Ваги ранжування скринінгу мусять давати 1 — інакше скор виходить
    за очікувану шкалу й пороги перестають читатись."""
    total = (
        config.WEIGHT_REVENUE_GROWTH + config.WEIGHT_EPS_GROWTH
        + config.WEIGHT_NEG_PE + config.WEIGHT_AVG_DOLLAR_VOLUME
    )
    assert total == 1


def test_pe_range_is_ordered():
    assert config.MIN_PE < config.MAX_PE


def test_single_config_has_no_module_level_siblings():
    """Прямий захист вимоги "конфіг один на весь агент": модульних
    config.py більше бути не повинно."""
    from pathlib import Path

    analysis_dir = Path(__file__).resolve().parent.parent
    strays = sorted(p.relative_to(analysis_dir) for p in analysis_dir.glob("*/config.py"))
    assert not strays, f"зʼявились модульні конфіги: {strays}"
