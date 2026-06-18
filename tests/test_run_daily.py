from __future__ import annotations

import sqlite3
import unittest
from datetime import date

from run_daily import trading_days_to_run
from virtual_trader.db import init_db, seed_defaults


def memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    seed_defaults(conn)
    return conn


class RunDailyCatchUpTest(unittest.TestCase):
    def test_catches_up_missing_business_days(self) -> None:
        conn = memory_db()
        conn.executemany(
            """
            INSERT INTO daily_reports (date, persona_id, market_summary, ai_summary, analysis, plan_text, review)
            VALUES (?, ?, 'm', 'a', 'analysis', 'plan', 'review')
            """,
            [
                ("2026-06-05", "quality"),
                ("2026-06-05", "momentum"),
                ("2026-06-05", "contrarian"),
            ],
        )
        conn.commit()

        result = trading_days_to_run(conn, date(2026, 6, 9))

        self.assertEqual(result, [date(2026, 6, 8), date(2026, 6, 9)])

    def test_reruns_latest_day_when_nothing_is_missing(self) -> None:
        conn = memory_db()
        conn.executemany(
            """
            INSERT INTO daily_reports (date, persona_id, market_summary, ai_summary, analysis, plan_text, review)
            VALUES (?, ?, 'm', 'a', 'analysis', 'plan', 'review')
            """,
            [
                ("2026-06-09", "quality"),
                ("2026-06-09", "momentum"),
                ("2026-06-09", "contrarian"),
            ],
        )
        conn.commit()

        result = trading_days_to_run(conn, date(2026, 6, 9))

        self.assertEqual(result, [date(2026, 6, 9)])


if __name__ == "__main__":
    unittest.main()
