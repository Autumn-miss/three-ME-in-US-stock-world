from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .config import INITIAL_CASH, MAX_OPEN_POSITIONS, MAX_POSITION_WEIGHT, MIN_CASH_WEIGHT, SLIPPAGE_RATE
from .db import one


@dataclass(frozen=True)
class Ohlc:
    open: float
    high: float
    low: float
    close: float


def buy_execution_price(limit_price: float, ohlc: Ohlc, slippage: float = SLIPPAGE_RATE) -> float | None:
    if ohlc.open <= limit_price:
        return round(min(limit_price, ohlc.open * (1 + slippage)), 2)
    if ohlc.low <= limit_price:
        return round(limit_price * (1 + slippage), 2)
    return None


def sell_execution_price(limit_price: float, ohlc: Ohlc, slippage: float = SLIPPAGE_RATE) -> float | None:
    if ohlc.open >= limit_price:
        return round(max(limit_price, ohlc.open * (1 - slippage)), 2)
    if ohlc.high >= limit_price:
        return round(limit_price * (1 - slippage), 2)
    return None


def get_cash(conn: sqlite3.Connection, persona_id: str) -> float:
    row = one(conn, "SELECT cash FROM personas WHERE id = ?", (persona_id,))
    if not row:
        raise ValueError(f"Unknown persona: {persona_id}")
    return float(row["cash"])


def set_cash(conn: sqlite3.Connection, persona_id: str, cash: float) -> None:
    conn.execute("UPDATE personas SET cash = ? WHERE id = ?", (cash, persona_id))


def get_position(conn: sqlite3.Connection, persona_id: str, symbol: str) -> tuple[float, float]:
    row = one(
        conn,
        "SELECT quantity, avg_cost FROM positions WHERE persona_id = ? AND symbol = ?",
        (persona_id, symbol),
    )
    if not row:
        return 0.0, 0.0
    return float(row["quantity"]), float(row["avg_cost"])


def upsert_position(conn: sqlite3.Connection, persona_id: str, symbol: str, quantity: float, avg_cost: float) -> None:
    if quantity <= 0.000001:
        conn.execute("DELETE FROM positions WHERE persona_id = ? AND symbol = ?", (persona_id, symbol))
        return
    conn.execute(
        """
        INSERT INTO positions (persona_id, symbol, quantity, avg_cost)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(persona_id, symbol)
        DO UPDATE SET quantity = excluded.quantity, avg_cost = excluded.avg_cost
        """,
        (persona_id, symbol, quantity, avg_cost),
    )


def latest_total_value(conn: sqlite3.Connection, persona_id: str) -> float:
    row = one(
        conn,
        """
        SELECT total_value FROM portfolio_snapshots
        WHERE persona_id = ?
        ORDER BY date DESC
        LIMIT 1
        """,
        (persona_id,),
    )
    return float(row["total_value"]) if row else INITIAL_CASH


def can_open_more_positions(conn: sqlite3.Connection, persona_id: str, symbol: str) -> bool:
    current_qty, _ = get_position(conn, persona_id, symbol)
    if current_qty > 0:
        return True
    row = one(
        conn,
        "SELECT COUNT(*) AS count FROM positions WHERE persona_id = ? AND quantity > 0",
        (persona_id,),
    )
    return int(row["count"]) < MAX_OPEN_POSITIONS


def place_order(
    conn: sqlite3.Connection,
    persona_id: str,
    symbol: str,
    side: str,
    quantity: float,
    limit_price: float,
    reason: str,
    plan_date: str,
    valid_date: str,
) -> int:
    side = side.upper()
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if limit_price <= 0:
        raise ValueError("limit_price must be positive")

    status = "PENDING"
    miss_reason = None
    if side == "BUY":
        cash = get_cash(conn, persona_id)
        projected_cost = quantity * limit_price * (1 + SLIPPAGE_RATE)
        total_value = latest_total_value(conn, persona_id)
        if projected_cost > cash:
            status = "REJECTED"
            miss_reason = "现金不足，规则层拒绝买入。"
        elif projected_cost > total_value * MAX_POSITION_WEIGHT:
            status = "REJECTED"
            miss_reason = "单股计划仓位超过上限。"
        elif cash - projected_cost < total_value * MIN_CASH_WEIGHT:
            status = "REJECTED"
            miss_reason = "买入后现金低于最低保留比例。"
        elif not can_open_more_positions(conn, persona_id, symbol):
            status = "REJECTED"
            miss_reason = "持仓数量超过上限。"
    else:
        held_qty, _ = get_position(conn, persona_id, symbol)
        if quantity > held_qty:
            status = "REJECTED"
            miss_reason = "卖出数量超过当前持仓，禁止做空。"

    cursor = conn.execute(
        """
        INSERT INTO orders (
            persona_id, symbol, side, quantity, limit_price, reason, plan_date, valid_date,
            status, miss_reason
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (persona_id, symbol, side, quantity, limit_price, reason, plan_date, valid_date, status, miss_reason),
    )
    return int(cursor.lastrowid)


def execute_order(conn: sqlite3.Connection, order: dict, ohlc: Ohlc, trade_date: str) -> None:
    if order["status"] != "PENDING":
        return
    side = order["side"]
    limit_price = float(order["limit_price"])
    price = buy_execution_price(limit_price, ohlc) if side == "BUY" else sell_execution_price(limit_price, ohlc)
    if price is None:
        conn.execute(
            """
            UPDATE orders
            SET status = 'EXPIRED', miss_reason = ?, execution_date = ?
            WHERE id = ?
            """,
            ("次日日内价格没有触及计划价，订单当日失效。", trade_date, order["id"]),
        )
        return

    persona_id = order["persona_id"]
    symbol = order["symbol"]
    quantity = float(order["quantity"])
    amount = round(quantity * price, 2)
    cash = get_cash(conn, persona_id)
    held_qty, avg_cost = get_position(conn, persona_id, symbol)

    if side == "BUY":
        if amount > cash:
            conn.execute(
                """
                UPDATE orders
                SET status = 'REJECTED', miss_reason = ?, execution_date = ?
                WHERE id = ?
                """,
                ("触发时现金不足，规则层拒绝成交。", trade_date, order["id"]),
            )
            return
        new_qty = held_qty + quantity
        new_avg = ((held_qty * avg_cost) + amount) / new_qty
        set_cash(conn, persona_id, cash - amount)
        upsert_position(conn, persona_id, symbol, new_qty, new_avg)
    else:
        if quantity > held_qty:
            conn.execute(
                """
                UPDATE orders
                SET status = 'REJECTED', miss_reason = ?, execution_date = ?
                WHERE id = ?
                """,
                ("触发时持仓不足，禁止做空。", trade_date, order["id"]),
            )
            return
        set_cash(conn, persona_id, cash + amount)
        upsert_position(conn, persona_id, symbol, held_qty - quantity, avg_cost)

    conn.execute(
        """
        UPDATE orders
        SET status = 'FILLED', execution_price = ?, execution_date = ?, miss_reason = NULL
        WHERE id = ?
        """,
        (price, trade_date, order["id"]),
    )
    conn.execute(
        """
        INSERT INTO trades (order_id, persona_id, symbol, side, quantity, price, amount, trade_date, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (order["id"], persona_id, symbol, side, quantity, price, amount, trade_date, order["reason"]),
    )


def execute_pending_orders(conn: sqlite3.Connection, run_date: str) -> None:
    pending = [
        dict(row)
        for row in conn.execute(
            """
            SELECT * FROM orders
            WHERE status = 'PENDING' AND valid_date <= ?
            ORDER BY id
            """,
            (run_date,),
        )
    ]
    for order in pending:
        row = one(
            conn,
            """
            SELECT open, high, low, close FROM market_prices
            WHERE symbol = ? AND date = ?
            """,
            (order["symbol"], run_date),
        )
        if not row:
            continue
        execute_order(
            conn,
            order,
            Ohlc(open=float(row["open"]), high=float(row["high"]), low=float(row["low"]), close=float(row["close"])),
            run_date,
        )


def create_snapshot(conn: sqlite3.Connection, persona_id: str, snap_date: str) -> None:
    cash = get_cash(conn, persona_id)
    positions_value = 0.0
    for row in conn.execute(
        """
        SELECT p.symbol, p.quantity, mp.close
        FROM positions p
        JOIN market_prices mp ON mp.symbol = p.symbol
        WHERE p.persona_id = ? AND mp.date = ?
        """,
        (persona_id, snap_date),
    ):
        positions_value += float(row["quantity"]) * float(row["close"])
    total_value = cash + positions_value
    previous = one(
        conn,
        """
        SELECT total_value FROM portfolio_snapshots
        WHERE persona_id = ? AND date < ?
        ORDER BY date DESC
        LIMIT 1
        """,
        (persona_id, snap_date),
    )
    prev_total = float(previous["total_value"]) if previous else INITIAL_CASH
    daily_return = (total_value / prev_total - 1) if prev_total else 0.0
    cumulative_return = total_value / INITIAL_CASH - 1
    high_water = one(
        conn,
        """
        SELECT MAX(total_value) AS high_water FROM portfolio_snapshots
        WHERE persona_id = ?
        """,
        (persona_id,),
    )
    max_total = max(float(high_water["high_water"] or INITIAL_CASH), total_value)
    drawdown = total_value / max_total - 1
    conn.execute(
        """
        INSERT INTO portfolio_snapshots (
            persona_id, date, cash, positions_value, total_value, daily_return,
            cumulative_return, drawdown
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(persona_id, date)
        DO UPDATE SET
            cash = excluded.cash,
            positions_value = excluded.positions_value,
            total_value = excluded.total_value,
            daily_return = excluded.daily_return,
            cumulative_return = excluded.cumulative_return,
            drawdown = excluded.drawdown
        """,
        (persona_id, snap_date, cash, positions_value, total_value, daily_return, cumulative_return, drawdown),
    )
