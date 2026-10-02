"""
Тести _common.py:mark_notified() — сама логіка (порожній список/білий
список таблиць), без реальної БД (фейковий conn/cursor)."""

import pytest

from _common import mark_notified


class _FakeCursor:
    def __init__(self):
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, query, params):
        self.executed.append((query, params))


class _FakeConn:
    def __init__(self):
        self.cursor_obj = _FakeCursor()
        self.committed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True


def test_mark_notified_noop_on_empty_ids():
    conn = _FakeConn()
    mark_notified(conn, "news_analysis", [])
    assert conn.cursor_obj.executed == []
    assert conn.committed is False


def test_mark_notified_rejects_unknown_table():
    conn = _FakeConn()
    with pytest.raises(ValueError):
        mark_notified(conn, "raw_observations", [1, 2])
    assert conn.cursor_obj.executed == []


@pytest.mark.parametrize(
    "table",
    [
        "news_analysis", "news_synthesis", "market_synthesis", "candidate_assets",
        "news_consolidated", "screening_results", "crypto_screening_candidates",
        "crypto_long_candidates",
    ],
)
def test_mark_notified_executes_update_for_known_tables(table):
    conn = _FakeConn()
    mark_notified(conn, table, [1, 2, 3])

    assert conn.committed is True
    assert len(conn.cursor_obj.executed) == 1
    query, params = conn.cursor_obj.executed[0]
    assert table in query
    assert "notified_at = now()" in query
    assert params == ([1, 2, 3],)
