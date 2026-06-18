from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .config import DATA_DIR, INITIAL_CASH, SYMBOLS


def connect(path: Path) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS personas (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            style TEXT NOT NULL,
            description TEXT NOT NULL,
            cash REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS symbols (
            symbol TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sector TEXT NOT NULL,
            ai_tags TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS market_prices (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL,
            PRIMARY KEY (symbol, date)
        );

        CREATE TABLE IF NOT EXISTS positions (
            persona_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            quantity REAL NOT NULL,
            avg_cost REAL NOT NULL,
            PRIMARY KEY (persona_id, symbol),
            FOREIGN KEY (persona_id) REFERENCES personas(id),
            FOREIGN KEY (symbol) REFERENCES symbols(symbol)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            persona_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
            quantity REAL NOT NULL,
            limit_price REAL NOT NULL,
            reason TEXT NOT NULL,
            plan_date TEXT NOT NULL,
            valid_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('PENDING', 'FILLED', 'EXPIRED', 'REJECTED')),
            execution_price REAL,
            execution_date TEXT,
            miss_reason TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (persona_id) REFERENCES personas(id),
            FOREIGN KEY (symbol) REFERENCES symbols(symbol)
        );

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            persona_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            amount REAL NOT NULL,
            trade_date TEXT NOT NULL,
            reason TEXT NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (persona_id) REFERENCES personas(id),
            FOREIGN KEY (symbol) REFERENCES symbols(symbol)
        );

        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            persona_id TEXT NOT NULL,
            date TEXT NOT NULL,
            cash REAL NOT NULL,
            positions_value REAL NOT NULL,
            total_value REAL NOT NULL,
            daily_return REAL NOT NULL,
            cumulative_return REAL NOT NULL,
            drawdown REAL NOT NULL,
            PRIMARY KEY (persona_id, date),
            FOREIGN KEY (persona_id) REFERENCES personas(id)
        );

        CREATE TABLE IF NOT EXISTS daily_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            persona_id TEXT NOT NULL,
            market_summary TEXT NOT NULL,
            ai_summary TEXT NOT NULL,
            analysis TEXT NOT NULL,
            plan_text TEXT NOT NULL,
            review TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (date, persona_id),
            FOREIGN KEY (persona_id) REFERENCES personas(id)
        );
        """
    )
    conn.commit()


def seed_defaults(conn: sqlite3.Connection) -> None:
    personas = [
        (
            "quality",
            "稳健质量型",
            "质量与风控",
            "偏好现金流稳定、护城河清晰的大型公司，低换手，优先控制回撤。",
        ),
        (
            "momentum",
            "成长动量型",
            "成长与趋势",
            "偏好增长、趋势和 AI 产业链中的强势标的，允许更高换手。",
        ),
        (
            "contrarian",
            "逆向价值型",
            "逆向与估值修复",
            "寻找大型股和 AI 产业链中短期回调、错杀或估值修复机会。",
        ),
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO personas (id, name, style, description, cash)
        VALUES (?, ?, ?, ?, ?)
        """,
        [(pid, name, style, desc, INITIAL_CASH) for pid, name, style, desc in personas],
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO symbols (symbol, name, sector, ai_tags)
        VALUES (?, ?, ?, ?)
        """,
        SYMBOLS,
    )
    conn.commit()


def reset_simulation(conn: sqlite3.Connection, clear_market_data: bool = True) -> None:
    conn.executescript(
        """
        DELETE FROM daily_reports;
        DELETE FROM trades;
        DELETE FROM orders;
        DELETE FROM portfolio_snapshots;
        DELETE FROM positions;
        """
    )
    if clear_market_data:
        conn.execute("DELETE FROM market_prices")
    conn.execute("UPDATE personas SET cash = ?", (INITIAL_CASH,))
    conn.commit()


def rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def one(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


def list_personas(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows(conn, "SELECT * FROM personas ORDER BY id")


def list_symbols(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows(conn, "SELECT *, ai_tags <> '' AS is_ai FROM symbols ORDER BY symbol")


def list_ai_symbols(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows(conn, "SELECT * FROM symbols WHERE ai_tags <> '' ORDER BY symbol")


def list_orders(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows(conn, "SELECT * FROM orders ORDER BY valid_date DESC, id DESC")


def list_trades(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows(conn, "SELECT * FROM trades ORDER BY trade_date DESC, id DESC")


def list_snapshots(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows(conn, "SELECT * FROM portfolio_snapshots ORDER BY date, persona_id")


def list_persona_reports(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows(conn, "SELECT * FROM daily_reports ORDER BY date DESC, persona_id")


def latest_price_map(conn: sqlite3.Connection) -> dict[str, float]:
    result: dict[str, float] = {}
    for row in conn.execute(
        """
        SELECT mp.symbol, mp.close
        FROM market_prices mp
        JOIN (
            SELECT symbol, MAX(date) AS date
            FROM market_prices
            GROUP BY symbol
        ) latest ON latest.symbol = mp.symbol AND latest.date = mp.date
        """
    ):
        result[row["symbol"]] = float(row["close"])
    return result


def price_source_summary(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows(
        conn,
        """
        SELECT source, COUNT(*) AS rows, MIN(date) AS first_date, MAX(date) AS last_date
        FROM market_prices
        GROUP BY source
        ORDER BY source
        """,
    )


def list_positions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    prices = latest_price_map(conn)
    out: list[dict[str, Any]] = []
    for row in conn.execute(
        """
        SELECT p.*, s.name AS company_name, s.sector, s.ai_tags
        FROM positions p
        JOIN symbols s ON s.symbol = p.symbol
        WHERE p.quantity > 0.000001
        ORDER BY p.persona_id, p.symbol
        """
    ):
        item = dict(row)
        last = prices.get(item["symbol"], item["avg_cost"])
        item["last_price"] = last
        item["market_value"] = item["quantity"] * last
        item["unrealized_pnl"] = item["quantity"] * (last - item["avg_cost"])
        out.append(item)
    return out
