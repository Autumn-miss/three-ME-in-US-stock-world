from __future__ import annotations

import sqlite3
import unittest

from virtual_trader.db import init_db, seed_defaults
from virtual_trader.engine import (
    Ohlc,
    buy_execution_price,
    execute_order,
    get_cash,
    get_position,
    place_order,
    sell_execution_price,
    set_cash,
    upsert_position,
)


def memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    seed_defaults(conn)
    return conn


class ExecutionPriceTest(unittest.TestCase):
    def test_buy_fills_near_open_when_open_below_limit(self) -> None:
        price = buy_execution_price(100, Ohlc(open=99, high=104, low=98, close=102), slippage=0.0005)
        self.assertEqual(price, 99.05)

    def test_buy_fills_when_low_touches_limit(self) -> None:
        price = buy_execution_price(100, Ohlc(open=103, high=104, low=99.5, close=101), slippage=0.0005)
        self.assertEqual(price, 100.05)

    def test_sell_fills_near_open_when_open_above_limit(self) -> None:
        price = sell_execution_price(100, Ohlc(open=101, high=103, low=98, close=99), slippage=0.0005)
        self.assertEqual(price, 100.95)

    def test_order_expires_when_limit_not_touched(self) -> None:
        self.assertIsNone(buy_execution_price(100, Ohlc(open=103, high=105, low=101, close=104)))


class RulesTest(unittest.TestCase):
    def test_rejects_buy_above_cash(self) -> None:
        conn = memory_db()
        order_id = place_order(conn, "quality", "NVDA", "BUY", 10_000, 100, "too much", "2026-01-01", "2026-01-02")
        row = conn.execute("SELECT status, miss_reason FROM orders WHERE id = ?", (order_id,)).fetchone()
        self.assertEqual(row["status"], "REJECTED")
        self.assertIn("现金不足", row["miss_reason"])

    def test_rejects_short_sell(self) -> None:
        conn = memory_db()
        order_id = place_order(conn, "quality", "NVDA", "SELL", 1, 100, "no shares", "2026-01-01", "2026-01-02")
        row = conn.execute("SELECT status, miss_reason FROM orders WHERE id = ?", (order_id,)).fetchone()
        self.assertEqual(row["status"], "REJECTED")
        self.assertIn("禁止做空", row["miss_reason"])

    def test_execute_buy_updates_cash_and_position(self) -> None:
        conn = memory_db()
        order_id = place_order(conn, "quality", "NVDA", "BUY", 10, 100, "buy", "2026-01-01", "2026-01-02")
        order = dict(conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())
        execute_order(conn, order, Ohlc(open=99, high=101, low=98, close=100), "2026-01-02")
        qty, avg = get_position(conn, "quality", "NVDA")
        self.assertEqual(qty, 10)
        self.assertEqual(round(avg, 2), 99.05)
        self.assertEqual(round(get_cash(conn, "quality"), 2), 19009.5)

    def test_execute_sell_updates_cash_and_position(self) -> None:
        conn = memory_db()
        set_cash(conn, "quality", 19_000)
        upsert_position(conn, "quality", "NVDA", 10, 100)
        order_id = place_order(conn, "quality", "NVDA", "SELL", 4, 110, "take profit", "2026-01-01", "2026-01-02")
        order = dict(conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())
        execute_order(conn, order, Ohlc(open=111, high=112, low=108, close=109), "2026-01-02")
        qty, avg = get_position(conn, "quality", "NVDA")
        self.assertEqual(qty, 6)
        self.assertEqual(avg, 100)
        self.assertEqual(round(get_cash(conn, "quality"), 2), 19443.76)


if __name__ == "__main__":
    unittest.main()
