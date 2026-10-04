from datetime import date
from decimal import Decimal

import pytest

import daily_digest
from daily_digest import (
    fetch_recent_candidates,
    fetch_recent_market_synthesis,
    fetch_recent_news_synthesis,
    fetch_recent_surprises,
    format_candidate_message,
    format_market_synthesis_message,
    format_news_synthesis_message,
    format_surprise_message,
)


def test_format_news_synthesis_message():
    row = {
        "asset_id": "xauusd",
        "cluster_count": 3,
        "net_lean": 2,
        "price_pct_change": Decimal("-1.64"),
        "price_start_date": date(2026, 9, 23),
        "price_end_date": date(2026, 9, 30),
        "direction": "down",
        "confidence": Decimal("0.55"),
        "summary": "Ціна впала на 1.64%, новинний сигнал змішаний.",
        "confirmation_factors": "Якщо падіння продовжиться без нових ведмежих новин — це вже не корекція.",
    }
    text = format_news_synthesis_message(row)
    assert "xauusd" in text
    assert "-1.64%" in text
    assert "2026-09-23" in text and "2026-09-30" in text
    assert "+2" in text
    assert "3 історій" in text
    assert "Ціна впала на 1.64%" in text
    assert "Перевірити: Якщо падіння продовжиться" in text


def test_format_news_synthesis_message_omits_confirmation_line_when_absent():
    row = {
        "asset_id": "wti_crude",
        "cluster_count": 1,
        "net_lean": 0,
        "price_pct_change": Decimal("0.0"),
        "price_start_date": date(2026, 9, 23),
        "price_end_date": date(2026, 9, 30),
        "direction": "neutral",
        "confidence": Decimal("0.3"),
        "summary": "Без руху.",
        "confirmation_factors": None,
    }
    text = format_news_synthesis_message(row)
    assert "Перевірити:" not in text


def test_format_market_synthesis_message():
    row = {"cluster_count": 8, "direction": "down", "confidence": Decimal("0.55"), "summary": "Risk-off стан."}
    text = format_market_synthesis_message(row)
    assert "risk-off" in text
    assert "0.55" in text
    assert "Risk-off стан." in text


def test_format_market_synthesis_message_unknown_direction_falls_back_to_raw():
    row = {"cluster_count": 1, "direction": "something_new", "confidence": Decimal("0.5"), "summary": "x"}
    text = format_market_synthesis_message(row)
    assert "something_new" in text


def test_format_surprise_message():
    row = {
        "metric_id": "cpi",
        "observed_at": date(2026, 9, 30),
        "actual_value": 0.397,
        "expected_value_raw": "0.4%",
        "expected_value_parsed": 0.4,
        "surprise": -0.003,
        "surprise_pct": -0.75,
    }
    text = format_surprise_message(row)
    assert "CPI (інфляція, США)" in text
    assert "0.397" in text
    assert "0.4%" in text


def test_format_surprise_message_omits_pct_when_none():
    row = {
        "metric_id": "unemployment_rate",
        "observed_at": date(2026, 9, 30),
        "actual_value": 4.1,
        "expected_value_raw": "4.1%",
        "expected_value_parsed": 4.1,
        "surprise": 0.0,
        "surprise_pct": None,
    }
    text = format_surprise_message(row)
    assert "%)" not in text.split("Сюрприз:")[1]


def test_format_candidate_message():
    row = {"ticker": "ACME", "company_name": "Acme Robotics Inc.", "reasoning": "New humanoid robot line."}
    text = format_candidate_message(row)
    assert "ACME" in text
    assert "Acme Robotics Inc." in text
    assert "New humanoid robot line." in text


# --- Regression 2026-09-28: daily_digest дублював notify_synthesis/
# notify_market_synthesis/notify_candidates/notify_expectations символ-в-
# символ, бо читав джерела сліпо за `created_at`-вікном, без урахування
# того, що окремі notify_*-джоби вже надіслали ці самі рядки й
# позначили notified_at. Тести нижче перевіряють САМЕ це: реальний SQL
# fetch_*-функцій і те, що main() дійсно викликає mark_notified/
# mark_expectations_notified (не просто форматує повідомлення).


class _FakeCursor:
    """Той самий підхід, що reporting/tests/test_news_notify.py:
    _FakeCursor — записує виконаний SQL, не звертається до реальної БД."""

    description = []  # порожній SELECT-результат — ці тести дивляться лише на виконаний SQL

    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, query, params=()):
        self._conn.executed.append((query, params))

    def fetchall(self):
        return []


class _FakeConn:
    def __init__(self):
        self.executed = []
        self.committed = 0

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.committed += 1

    def close(self):
        pass


@pytest.mark.parametrize(
    "fetch_fn, extra_args",
    [
        (fetch_recent_news_synthesis, ()),
        (fetch_recent_market_synthesis, ()),
        (fetch_recent_surprises, ()),
        (fetch_recent_candidates, ()),
    ],
)
def test_fetch_functions_filter_out_already_notified_rows(fetch_fn, extra_args):
    """Реальний SQL, не мокнутий: доводить, що кожне з 4 джерел
    daily_digest тепер виключає рядки, які вже надіслала окрема
    notify_*-джоба, а не тільки бере "усе за --hours"."""
    conn = _FakeConn()
    fetch_fn(conn, 24, *extra_args)
    assert len(conn.executed) == 1
    query, params = conn.executed[0]
    assert "notified_at IS NULL" in query
    assert params[0] == 24


def _news_row(id=1):
    return {
        "id": id, "asset_id": "xauusd", "cluster_count": 1, "net_lean": 1,
        "price_pct_change": Decimal("-1.33"),
        "price_start_date": date(2026, 9, 23), "price_end_date": date(2026, 9, 30),
        "direction": "up", "confidence": Decimal("0.6"),
        "summary": "Бичача новина суперечить падінню ціни.",
        "confirmation_factors": "Перевірити, чи рух продовжиться без нових новин.",
    }


def _market_row(id=2):
    return {"id": id, "cluster_count": 8, "direction": "neutral", "confidence": Decimal("0.35"), "summary": "Збалансовано."}


def _surprise_row(id=3):
    return {
        "id": id, "metric_id": "cpi", "observed_at": date(2026, 9, 28), "actual_value": 0.4,
        "expected_value_raw": "0.3%", "expected_value_parsed": 0.3, "surprise": 0.1, "surprise_pct": 33.3,
    }


def _candidate_row(id=4):
    return {"id": id, "ticker": "ACME", "company_name": "Acme Robotics", "reasoning": "New product line."}


def _patch_digest_sources(monkeypatch, conn, sent, *, news=(), market=None, surprises=(), candidates=()):
    monkeypatch.setattr(daily_digest, "resolve_telegram_credentials", lambda: ("token", "chat"))
    monkeypatch.setattr(daily_digest, "get_connection", lambda: conn)
    monkeypatch.setattr(
        daily_digest, "send_telegram_message",
        lambda token, chat_id, text, parse_mode=None: sent.append(text),
    )
    monkeypatch.setattr(daily_digest, "fetch_recent_news_synthesis", lambda conn, hours: list(news))
    monkeypatch.setattr(daily_digest, "fetch_recent_market_synthesis", lambda conn, hours: market)
    monkeypatch.setattr(daily_digest, "fetch_recent_surprises", lambda conn, hours: list(surprises))
    monkeypatch.setattr(daily_digest, "fetch_recent_candidates", lambda conn, hours: list(candidates))
    monkeypatch.setattr("sys.argv", ["daily_digest.py"])


def test_main_marks_every_sent_row_notified_via_real_sql(monkeypatch):
    """Наскрізно: fetch_* підмінені (щоб не залежати від реальної БД), а
    mark_notified()/mark_expectations_notified() лишаються РЕАЛЬНИМИ —
    перевіряє фактичний UPDATE SQL, виконаний після кожної відправки, а
    не просто факт виклику мокнутої функції."""
    conn = _FakeConn()
    sent = []
    _patch_digest_sources(
        monkeypatch, conn, sent,
        news=[_news_row(1)], market=_market_row(2), surprises=[_surprise_row(3)], candidates=[_candidate_row(4)],
    )

    daily_digest.main()

    assert len(sent) == 4  # market іде першим повідомленням, далі news/surprises/candidates
    update_queries = {q: p for q, p in conn.executed}
    market_update = next(q for q, p in conn.executed if "market_synthesis" in q and "UPDATE" in q)
    news_update = next(q for q, p in conn.executed if "news_synthesis" in q and "UPDATE" in q)
    expectation_update = next(q for q, p in conn.executed if "expectation_comparisons" in q and "UPDATE" in q)
    candidate_update = next(q for q, p in conn.executed if "candidate_assets" in q and "UPDATE" in q)
    assert update_queries[market_update] == ([2],)
    assert update_queries[news_update] == ([1],)
    assert update_queries[expectation_update] == ([3],)
    assert update_queries[candidate_update] == ([4],)
    assert conn.committed == 4  # один commit на кожен mark_notified/mark_expectations_notified виклик


def test_main_sends_fallback_and_marks_nothing_when_all_already_notified(monkeypatch):
    """Регресія: до фіксу цей сценарій був НЕДОСЯЖНИЙ — daily_digest
    завжди щось знаходив у 24-годинному вікні, навіть якщо notify_*-джоби
    вже все надіслали. Тепер порожній `notified_at IS NULL`-результат —
    штатний випадок, і жодного зайвого UPDATE не виконується."""
    conn = _FakeConn()
    sent = []
    _patch_digest_sources(monkeypatch, conn, sent)  # усі джерела порожні

    daily_digest.main()

    assert sent == ["Сьогодні суттєвих подій не було."]
    assert conn.executed == []
    assert conn.committed == 0


def test_main_marks_earlier_rows_notified_even_if_a_later_send_fails(monkeypatch):
    """Доводить, що позначення notified_at відбувається ОДРАЗУ після
    кожного повідомлення (не одним батчем наприкінці) — інакше
    мережевий збій на 2-му з 2 повідомлень змусив би наступний прогін
    надіслати вже успішно доставлений перший рядок вдруге."""
    conn = _FakeConn()
    sent = []

    def flaky_send(token, chat_id, text, parse_mode=None):
        sent.append(text)
        if len(sent) == 2:
            raise ConnectionError("simulated Telegram outage")

    monkeypatch.setattr(daily_digest, "resolve_telegram_credentials", lambda: ("token", "chat"))
    monkeypatch.setattr(daily_digest, "get_connection", lambda: conn)
    monkeypatch.setattr(daily_digest, "send_telegram_message", flaky_send)
    monkeypatch.setattr(daily_digest, "fetch_recent_news_synthesis", lambda conn, hours: [_news_row(1), _news_row(5)])
    monkeypatch.setattr(daily_digest, "fetch_recent_market_synthesis", lambda conn, hours: None)
    monkeypatch.setattr(daily_digest, "fetch_recent_surprises", lambda conn, hours: [])
    monkeypatch.setattr(daily_digest, "fetch_recent_candidates", lambda conn, hours: [])
    monkeypatch.setattr("sys.argv", ["daily_digest.py"])

    with pytest.raises(ConnectionError):
        daily_digest.main()

    assert len(sent) == 2  # другий виклик і кинув виняток, але це вже ПІСЛЯ send
    news_updates = [(q, p) for q, p in conn.executed if "news_synthesis" in q]
    assert len(news_updates) == 1  # лише перший рядок (id=1) встиг позначитись
    assert news_updates[0][1] == ([1],)
