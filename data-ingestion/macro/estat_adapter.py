"""
Адаптер e-Stat (政府統計の総合窓口) API v3.0 — офіційне першоджерело
для CPI Японії. https://www.e-stat.go.jp/api/

Четвертий адаптер проєкту. На відміну від FRED/ECB/BOJ, тут ключ
(`appId`) обов'язковий — безкоштовна реєстрація на e-stat.go.jp,
до 3 appId на акаунт. Передається через ESTAT_APP_ID у .env, за тим
самим патерном, що й FRED_API_KEY.

СТАТИСТИЧНА ТАБЛИЦЯ: 2025年基準消費者物価指数 (CPI, база 2025=100,
чинна з 21.08.2026), statsDataId=0004052037. Старий statsDataId
0003427113 (база 2020=100) продовжує оновлюватись лише до грудня
2026 — після цього чинним лишається тільки новий (див.
docs/decisions.md, запис про базову ревізію Японія CPI, той самий
сценарій, що й з ECB ICP→HICP).

ЧОМУ ДВА МЕРЕЖЕВІ ВИКЛИКИ В fetch(): на відміну від FRED/ECB/BOJ, де
код серії відомий заздалегідь, e-Stat ідентифікує зріз даних кодами
класифікації (area = регіон, cat01 = стаття витрат), які видаються
разом із самими даними як метадані (CLASS_INF), а не документовані
окремо у зручному вигляді. Тому:
  1) невеликий запит (limit=1, metaGetFlg=Y) — тільки щоб отримати
     CLASS_INF і по ньому знайти код "全国" (національний) в area та
     код "総合" (усі товари) в cat01;
  2) основний запит уже з конкретними cdArea/cdCat01 — компактна
     відповідь тільки з потрібним рядом.
Це захищає від жорсткого хардкоду кодів класифікації, які не вдалось
підтвердити заздалегідь (мережа пісочниці Claude не мала доступу до
e-stat.go.jp) — і які теоретично можуть відрізнятись між
statsDataId. Перед першим комітом обов'язково звірити результат
живим запитом (той самий протокол, що й для BOJ/ECB).
"""

import logging
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import requests

from common.adapter import BaseAdapter, NormalizedRecord

logger = logging.getLogger(__name__)

ESTAT_API_URL = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"

# metric_id → statsDataId. Для кожного нового Японія-показника з
# e-Stat (напр. Unemployment Rate) достатньо додати новий рядок тут —
# резолюція area/cat01 і парсинг залишаються спільні.
METRICS: dict[str, str] = {
    "japan_cpi": "0004052037",  # 2025年基準消費者物価指数, 総合, 全国
}

# Назви, за якими шукаємо потрібний зріз у метаданих CLASS_INF —
# людинозрозумілі рядки стабільніші за самі коди, які можуть
# відрізнятись між таблицями/базовими роками.
_NATIONAL_AREA_NAME = "全国"
_ALL_ITEMS_CAT_NAME = "総合"

_TIME_PATTERNS = (
    re.compile(r"(\d{4})年(\d{1,2})月"),  # "2026年07月" → місячний
    re.compile(r"^(\d{4})(\d{2})$"),       # "202607" (про всяк випадок)
)


def _parse_estat_time(name: str) -> Optional[date]:
    for pattern in _TIME_PATTERNS:
        match = pattern.search(name)
        if match:
            year, month = int(match.group(1)), int(match.group(2))
            return date(year, month, 1)
    return None


def _find_class_code(class_inf: Any, class_id: str, name_needle: str) -> Optional[str]:
    """Шукає в CLASS_INF.CLASS_OBJ об'єкт з @id == class_id, і в
    ньому — CLASS-запис, чия @name точно дорівнює name_needle
    (пріоритет) або містить його (фолбек, якщо точного співпадіння
    немає — деякі таблиці додають примітки в дужках до назви)."""
    class_objs = class_inf.get("CLASS_OBJ") if isinstance(class_inf, dict) else None
    if class_objs is None:
        return None
    if isinstance(class_objs, dict):
        class_objs = [class_objs]

    for obj in class_objs:
        if obj.get("@id") != class_id:
            continue
        entries = obj.get("CLASS")
        if isinstance(entries, dict):
            entries = [entries]
        entries = entries or []

        for entry in entries:
            if entry.get("@name") == name_needle:
                return entry.get("@code")
        for entry in entries:
            if name_needle in (entry.get("@name") or ""):
                return entry.get("@code")
    return None


def _get_class_name(class_inf: Any, class_id: str, code: str) -> Optional[str]:
    class_objs = class_inf.get("CLASS_OBJ") if isinstance(class_inf, dict) else None
    if isinstance(class_objs, dict):
        class_objs = [class_objs]
    for obj in class_objs or []:
        if obj.get("@id") != class_id:
            continue
        entries = obj.get("CLASS")
        if isinstance(entries, dict):
            entries = [entries]
        for entry in entries or []:
            if entry.get("@code") == code:
                return entry.get("@name")
    return None


class EstatAdapter(BaseAdapter):
    source = "estat"

    def __init__(self, api_key: str, metric_id: str, session: Optional[requests.Session] = None):
        # Параметр названо api_key (не app_id), щоб збігатись зі
        # спільним патерном інстанціації в run_collect.py/collect_all.py
        # (той самий, що й у FredAdapter) — по суті це appId e-Stat.
        if not api_key:
            raise ValueError(
                "ESTAT_APP_ID не задано. Зареєструйте безкоштовний appId на "
                "https://www.e-stat.go.jp (My Page → API機能 → "
                "アプリケーションIDの発行) і додайте його в .env."
            )
        if metric_id not in METRICS:
            raise ValueError(
                f"Невідомий metric_id для e-Stat: {metric_id!r}. "
                f"Доступні: {sorted(METRICS)}"
            )
        self.app_id = api_key
        self.metric_id = metric_id
        self.stats_data_id = METRICS[metric_id]
        self.session = session or requests.Session()

    def _resolve_area_and_cat01(self) -> tuple[str, str]:
        """Крок 1: невеликий запит лише за метаданими, щоб знайти коди
        "全国" (area) і "総合" (cat01) для цього statsDataId."""
        params = {
            "appId": self.app_id,
            "statsDataId": self.stats_data_id,
            "metaGetFlg": "Y",
            "cntGetFlg": "N",
            "limit": 1,
        }
        response = self.session.get(ESTAT_API_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()

        stats_data = payload.get("GET_STATS_DATA", {}).get("STATISTICAL_DATA", {})
        class_inf = stats_data.get("CLASS_INF", {})

        area_code = _find_class_code(class_inf, "area", _NATIONAL_AREA_NAME)
        cat01_code = _find_class_code(class_inf, "cat01", _ALL_ITEMS_CAT_NAME)

        if not area_code or not cat01_code:
            raise ValueError(
                f"Не вдалось знайти код area='{_NATIONAL_AREA_NAME}' і/або "
                f"cat01='{_ALL_ITEMS_CAT_NAME}' у метаданих e-Stat для "
                f"statsDataId={self.stats_data_id} (area_code={area_code!r}, "
                f"cat01_code={cat01_code!r}). Структура класифікації цієї "
                f"таблиці могла відрізнятись від очікуваної — перевірте "
                f"вручну через getMetaInfo."
            )
        return area_code, cat01_code

    def fetch(
        self,
        limit: Optional[int] = None,
        observation_start: Optional[str] = None,
        observation_end: Optional[str] = None,
    ) -> Any:
        area_code, cat01_code = self._resolve_area_and_cat01()

        params: dict[str, Any] = {
            "appId": self.app_id,
            "statsDataId": self.stats_data_id,
            "cdArea": area_code,
            "cdCat01": cat01_code,
            "metaGetFlg": "Y",  # лишаємо Y — normalize() використовує CLASS_INF для дат
            "cntGetFlg": "N",
        }
        # e-Stat не має limit "останні N" так само зручно, як FRED
        # (limit тут — "перші N рядків результату", не "останні") —
        # тому свідомо не передаємо limit сюди; фільтрація за limit
        # відбувається в normalize() після отримання повного ряду.

        response = self.session.get(ESTAT_API_URL, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def normalize(self, raw_response: Any, limit: Optional[int] = None) -> list[NormalizedRecord]:
        fetched_at = datetime.now(timezone.utc)
        records: list[NormalizedRecord] = []

        stats_data = raw_response.get("GET_STATS_DATA", {}).get("STATISTICAL_DATA", {})
        class_inf = stats_data.get("CLASS_INF", {})
        data_inf = stats_data.get("DATA_INF", {})
        values = data_inf.get("VALUE", [])
        if isinstance(values, dict):
            values = [values]

        if not values:
            logger.warning(
                "Порожній DATA_INF.VALUE у відповіді e-Stat для %s "
                "(statsDataId=%s) — перевірте параметри запиту.",
                self.metric_id, self.stats_data_id,
            )
            return records

        for entry in values:
            raw_value = entry.get("$")
            if raw_value in (None, "", "-", "..."):
                continue

            try:
                value = Decimal(str(raw_value))
            except InvalidOperation:
                logger.warning(
                    "Не вдалось розпарсити значення e-Stat %s: %r",
                    self.metric_id, raw_value,
                )
                continue

            time_code = entry.get("@time")
            time_name = _get_class_name(class_inf, "time", time_code) or str(time_code)
            observed_at = _parse_estat_time(time_name)
            if observed_at is None:
                logger.warning(
                    "Не вдалось розпарсити період e-Stat %r (код %r) для %s",
                    time_name, time_code, self.metric_id,
                )
                continue

            records.append(
                NormalizedRecord(
                    source=self.source,
                    metric_id=self.metric_id,
                    value=value,
                    observed_at=observed_at,
                    fetched_at=fetched_at,
                    revision=None,
                    raw_payload=dict(entry),
                )
            )

        records.sort(key=lambda r: r.observed_at)
        if limit:
            records = records[-limit:]
        return records

    def collect(self, **kwargs) -> list[NormalizedRecord]:
        limit = kwargs.pop("limit", None)
        raw = self.fetch(**kwargs)
        return self.normalize(raw, limit=limit)
