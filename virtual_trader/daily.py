from __future__ import annotations

import sqlite3
from datetime import date

from .config import INDEX_SYMBOLS
from .db import list_personas, list_symbols, one, rows
from .engine import create_snapshot, execute_pending_orders
from .llm import optional_llm_note
from .market_data import get_daily_price
from .news import build_ai_summary, build_market_summary
from .strategies import decision_log_for_orders, generate_orders_for_persona, persona_analysis, plan_text_for_orders


def ensure_market_data_for_date(conn: sqlite3.Connection, day: date, allow_synthetic: bool = False) -> None:
    symbols = [row["symbol"] for row in list_symbols(conn)] + INDEX_SYMBOLS
    for symbol in symbols:
        existing = one(
            conn,
            "SELECT symbol FROM market_prices WHERE symbol = ? AND date = ?",
            (symbol, day.isoformat()),
        )
        if existing:
            continue
        price = get_daily_price(symbol, day, allow_synthetic=allow_synthetic)
        conn.execute(
            """
            INSERT OR REPLACE INTO market_prices (symbol, date, open, high, low, close, volume, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                price["symbol"],
                price["date"],
                price["open"],
                price["high"],
                price["low"],
                price["close"],
                price["volume"],
                price["source"],
            ),
        )
    conn.commit()


def index_moves(conn: sqlite3.Connection, day: date) -> dict[str, float]:
    today = day.isoformat()
    previous = one(conn, "SELECT MAX(date) AS date FROM market_prices WHERE date < ?", (today,))
    prev_date = previous["date"] if previous else None
    moves: dict[str, float] = {}
    if not prev_date:
        return moves
    for symbol in INDEX_SYMBOLS:
        row = one(
            conn,
            """
            SELECT now.close AS close, prev.close AS prev_close
            FROM market_prices now
            JOIN market_prices prev ON prev.symbol = now.symbol AND prev.date = ?
            WHERE now.symbol = ? AND now.date = ?
            """,
            (prev_date, symbol, today),
        )
        if row and row["prev_close"]:
            moves[symbol] = float(row["close"]) / float(row["prev_close"]) - 1
    return moves


def ai_movers(conn: sqlite3.Connection, day: date) -> list[dict]:
    today = day.isoformat()
    previous = one(conn, "SELECT MAX(date) AS date FROM market_prices WHERE date < ?", (today,))
    prev_date = previous["date"] if previous else None
    if not prev_date:
        return []
    result = []
    for row in rows(
        conn,
        """
        SELECT s.symbol, s.ai_tags, now.close AS close, prev.close AS prev_close
        FROM symbols s
        JOIN market_prices now ON now.symbol = s.symbol AND now.date = ?
        JOIN market_prices prev ON prev.symbol = s.symbol AND prev.date = ?
        WHERE s.ai_tags <> ''
        """,
        (today, prev_date),
    ):
        result.append(
            {
                "symbol": row["symbol"],
                "ai_tags": row["ai_tags"],
                "return": float(row["close"]) / float(row["prev_close"]) - 1,
            }
        )
    return result


def recent_execution_review(conn: sqlite3.Connection, persona_id: str, day: date) -> str:
    items = rows(
        conn,
        """
        SELECT symbol, side, status, execution_price, miss_reason
        FROM orders
        WHERE persona_id = ? AND execution_date = ?
        ORDER BY id
        """,
        (persona_id, day.isoformat()),
    )
    if not items:
        return "今日没有到期订单需要复盘。"
    lines = []
    for item in items:
        if item["status"] == "FILLED":
            lines.append(f"{item['side']} {item['symbol']} 已成交，价格 {item['execution_price']:.2f}。")
        else:
            lines.append(f"{item['side']} {item['symbol']} 未成交：{item['miss_reason']}")
    return "\n".join(f"- {line}" for line in lines)


def upsert_report(
    conn: sqlite3.Connection,
    day: date,
    persona_id: str,
    market_summary: str,
    ai_summary: str,
    analysis: str,
    plan_text: str,
    review: str,
) -> None:
    llm = optional_llm_note(
        f"请用中文给虚拟美股投资人写一段不超过120字的投资日记。人格={persona_id}。"
        f"市场={market_summary}。AI产业链={ai_summary}。计划={plan_text}。"
    )
    if llm:
        analysis = f"{analysis}\n\nLLM 日记：{llm}"
    conn.execute(
        """
        INSERT INTO daily_reports (date, persona_id, market_summary, ai_summary, analysis, plan_text, review)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date, persona_id)
        DO UPDATE SET
            market_summary = excluded.market_summary,
            ai_summary = excluded.ai_summary,
            analysis = excluded.analysis,
            plan_text = excluded.plan_text,
            review = excluded.review
        """,
        (day.isoformat(), persona_id, market_summary, ai_summary, analysis, plan_text, review),
    )


def already_planned(conn: sqlite3.Connection, persona_id: str, day: date) -> bool:
    row = one(
        conn,
        "SELECT id FROM orders WHERE persona_id = ? AND plan_date = ? LIMIT 1",
        (persona_id, day.isoformat()),
    )
    return row is not None


def run_daily(conn: sqlite3.Connection, day: date, allow_synthetic: bool = False) -> None:
    ensure_market_data_for_date(conn, day, allow_synthetic=allow_synthetic)
    execute_pending_orders(conn, day.isoformat())

    market_summary = build_market_summary(index_moves(conn, day))
    ai_summary = build_ai_summary(day, ai_movers(conn, day))

    for persona in list_personas(conn):
        create_snapshot(conn, persona["id"], day.isoformat())
        if already_planned(conn, persona["id"], day):
            order_rows = rows(
                conn,
                "SELECT id FROM orders WHERE persona_id = ? AND plan_date = ? ORDER BY id",
                (persona["id"], day.isoformat()),
            )
            order_ids = [int(row["id"]) for row in order_rows]
        else:
            order_ids = generate_orders_for_persona(conn, persona["id"], day)
        analysis = persona_analysis(conn, persona["id"], day, market_summary, ai_summary)
        plan_text = decision_log_for_orders(conn, persona["id"], order_ids)
        review = recent_execution_review(conn, persona["id"], day)
        upsert_report(conn, day, persona["id"], market_summary, ai_summary, analysis, plan_text, review)
        create_snapshot(conn, persona["id"], day.isoformat())

    conn.commit()
