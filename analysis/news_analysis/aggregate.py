"""
Детермінована агрегація вже класифікованих новин (news_analysis) —
БЕЗ LLM, звичайний код (analysis/CLAUDE.md: "числові порівняння,
тренди — звичайний код, без LLM"). Два кроки:

1. cluster_articles() — групує статті про ОДНУ Й ТУ САМУ історію,
   передану різними виданнями (живий приклад 2026-09-26: та сама
   wire-стрічка "Asian shares mixed after global bond sell-off"
   прийшла ~6 разів з різних сайтів — без цього кроку щоденний
   дайджест складався б із повторів, docs/decisions.md, 2026-09-26
   "визначено 5 цілей news/").
2. aggregate_by_asset() — зводить кластери по asset_id: скільки
   кластерів up/down/neutral/unclear на актив за вікно.

Розмір кластера (скільки видань написали) — природна, безкоштовна
шкала значущості: подія, яку підхопили 6 видань, об'єктивно
важливіша за ту, що згадало одне. Це замінює відсутню "шкалу
важливості" без додаткового LLM-виклику (docs/news-purpose.md,
ціль 5).
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher

_DIRECTIONS = ("up", "down", "neutral", "unclear")

# Наскільки схожими мають бути нормалізовані заголовки, щоб рахувати
# їх тією самою історією. 0.7 — емпіричний запас: живі дублікати були
# або ідентичним wire-текстом (ratio ~1.0), або дуже близькі
# перефразування; різні статті про той самий актив (напр. два різні
# дописи про ціну золота) зазвичай мають значно нижчий ratio.
DEFAULT_SIMILARITY_THRESHOLD = 0.7


@dataclass
class NewsCluster:
    representative_title: str
    source_count: int
    asset_ids: list[str]
    dominant_direction: str
    direction_counts: dict[str, int]
    summaries: list[str]
    urls: list[str]
    earliest_published_at: datetime
    latest_published_at: datetime
    raw_news_ids: list[int] = field(default_factory=list)


@dataclass
class AssetSignal:
    asset_id: str
    cluster_count: int
    direction_counts: dict[str, int]
    net_lean: int  # up_кластери - down_кластери, серед КЛАСТЕРІВ, не сирих статей
    summaries: list[str]


def normalize_title(title: str) -> str:
    """Нижній регістр, без пунктуації — усуває розбіжності в
    пунктуації/регістрі між виданнями, що передають ту саму
    wire-стрічку. `\\w` (не `a-z0-9`!) — Unicode word characters,
    зберігає нелатинський текст (гінді/китайська/грецька/турецька):
    жива перевірка 2026-09-26 показала, що `a-z0-9`-only regex
    перетворював майже ВЕСЬ нелатинський заголовок на порожній/
    майже порожній рядок — два випадкові короткі "порожні" залишки
    від зовсім різних історій (заголовок про нафту гінді й заголовок
    про дохідність облігацій Японії) отримували штучно високий
    SequenceMatcher ratio і хибно об'єднувались в один кластер."""
    return re.sub(r"[^\w\s]", "", title.lower()).strip()


# Захист від того самого класу помилки: нормалізований рядок коротший
# за цей порядок ніколи не порівнюється на схожість (завжди починає
# власний кластер) — короткі/вироджені рядки (в т.ч. нелатинський
# текст, що після нормалізації лишає тільки цифри/пробіли) занадто
# легко дають штучно високий ratio з чимось геть не пов'язаним.
MIN_NORMALIZED_LENGTH_FOR_MATCHING = 15


def _title_similarity(a: str, b: str) -> float:
    if len(a) < MIN_NORMALIZED_LENGTH_FOR_MATCHING or len(b) < MIN_NORMALIZED_LENGTH_FOR_MATCHING:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def cluster_articles(
    articles: list[dict], similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
) -> list[NewsCluster]:
    """Групує статті з однаковою/дуже схожою нормалізованою назвою в
    один NewsCluster. Жадібний single-linkage: порівнює з
    representative (першою статтею) кожного вже існуючого кластера —
    O(n*k), де k — к-сть кластерів, достатньо для обсягів news/ (сотні
    статей на прогін, не мільйони).

    articles — список dict з ключами title/url/published_at/asset_id/
    direction/summary/raw_news_id (той самий формат, що повертає
    _db.py:fetch_relevant_for_aggregation()). Порядок вхідного списку
    не важливий — кластери сортуються за latest_published_at DESC на
    виході.
    """
    groups: list[list[dict]] = []
    normalized_representatives: list[str] = []

    for article in articles:
        normalized = normalize_title(article["title"])
        placed = False
        for i, rep in enumerate(normalized_representatives):
            if _title_similarity(normalized, rep) >= similarity_threshold:
                groups[i].append(article)
                placed = True
                break
        if not placed:
            groups.append([article])
            normalized_representatives.append(normalized)

    clusters = [_build_cluster(group) for group in groups]
    clusters.sort(key=lambda c: c.latest_published_at, reverse=True)
    return clusters


def _build_cluster(group: list[dict]) -> NewsCluster:
    # Найдовший заголовок як представник — зазвичай найбільш повний
    # (короткі часто урізані для соцмереж/агрегаторів).
    representative = max(group, key=lambda a: len(a["title"]))

    asset_ids = sorted({a["asset_id"] for a in group if a.get("asset_id")})

    direction_counts = {d: 0 for d in _DIRECTIONS}
    for a in group:
        direction_counts[a["direction"]] = direction_counts.get(a["direction"], 0) + 1
    dominant_direction = _dominant_direction(direction_counts)

    summaries = list(dict.fromkeys(a["summary"] for a in group if a.get("summary")))
    urls = [a["url"] for a in group]
    published_dates = [a["published_at"] for a in group]
    raw_news_ids = [a["raw_news_id"] for a in group if "raw_news_id" in a]

    return NewsCluster(
        representative_title=representative["title"],
        source_count=len(group),
        asset_ids=asset_ids,
        dominant_direction=dominant_direction,
        direction_counts=direction_counts,
        summaries=summaries,
        urls=urls,
        earliest_published_at=min(published_dates),
        latest_published_at=max(published_dates),
        raw_news_ids=raw_news_ids,
    )


def _dominant_direction(direction_counts: dict[str, int]) -> str:
    """Найчастіший напрямок серед статей кластера, крім "unclear" —
    якщо є хоч один визначений сигнал (up/down/neutral), він
    важливіший за "незрозуміло". "unclear" домінує тільки якщо це
    взагалі все, що є."""
    decisive = {d: c for d, c in direction_counts.items() if d != "unclear" and c > 0}
    if decisive:
        return max(decisive, key=decisive.get)
    return "unclear"


def aggregate_by_asset(clusters: list[NewsCluster]) -> dict[str, AssetSignal]:
    """Зводить кластери по asset_id: скільки КЛАСТЕРІВ (не сирих
    статей — дублікати вже об'єднані) мають кожен напрямок для
    активу. net_lean = up - down серед кластерів, де актив згаданий —
    швидкий, зрозумілий числовий сигнал без LLM."""
    by_asset: dict[str, list[NewsCluster]] = {}
    for cluster in clusters:
        for asset_id in cluster.asset_ids:
            by_asset.setdefault(asset_id, []).append(cluster)

    signals: dict[str, AssetSignal] = {}
    for asset_id, asset_clusters in by_asset.items():
        direction_counts = {d: 0 for d in _DIRECTIONS}
        summaries: list[str] = []
        for cluster in asset_clusters:
            direction_counts[cluster.dominant_direction] += 1
            summaries.extend(cluster.summaries)

        signals[asset_id] = AssetSignal(
            asset_id=asset_id,
            cluster_count=len(asset_clusters),
            direction_counts=direction_counts,
            net_lean=direction_counts["up"] - direction_counts["down"],
            summaries=summaries,
        )

    return signals
