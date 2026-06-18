from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from .config import MAX_POSITION_WEIGHT
from .db import one, rows
from .engine import get_cash, get_position, latest_total_value, place_order
from .market_data import next_business_day


@dataclass(frozen=True)
class Candidate:
    symbol: str
    close: float
    open: float
    high: float
    low: float
    day_return: float
    ai_tags: str
    sector: str


def market_candidates(conn: sqlite3.Connection, day: date) -> list[Candidate]:
    today = day.isoformat()
    previous = one(conn, "SELECT MAX(date) AS date FROM market_prices WHERE date < ?", (today,))
    prev_date = previous["date"] if previous else None
    out: list[Candidate] = []
    for row in rows(
        conn,
        """
        SELECT s.symbol, s.sector, s.ai_tags, mp.open, mp.high, mp.low, mp.close,
               prev.close AS prev_close
        FROM symbols s
        JOIN market_prices mp ON mp.symbol = s.symbol AND mp.date = ?
        LEFT JOIN market_prices prev ON prev.symbol = s.symbol AND prev.date = ?
        ORDER BY s.symbol
        """,
        (today, prev_date),
    ):
        prev_close = float(row["prev_close"] or row["open"])
        day_return = float(row["close"]) / prev_close - 1 if prev_close else 0.0
        out.append(
            Candidate(
                symbol=row["symbol"],
                close=float(row["close"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                day_return=day_return,
                ai_tags=row["ai_tags"],
                sector=row["sector"],
            )
        )
    return out


def open_positions(conn: sqlite3.Connection, persona_id: str, day: date) -> list[dict]:
    return rows(
        conn,
        """
        SELECT p.symbol, p.quantity, p.avg_cost, mp.close, s.ai_tags
        FROM positions p
        JOIN market_prices mp ON mp.symbol = p.symbol AND mp.date = ?
        JOIN symbols s ON s.symbol = p.symbol
        WHERE p.persona_id = ? AND p.quantity > 0
        ORDER BY p.symbol
        """,
        (day.isoformat(), persona_id),
    )


def has_pending_order(conn: sqlite3.Connection, persona_id: str, symbol: str) -> bool:
    row = one(
        conn,
        """
        SELECT id FROM orders
        WHERE persona_id = ? AND symbol = ? AND status = 'PENDING'
        LIMIT 1
        """,
        (persona_id, symbol),
    )
    return row is not None


def target_quantity(conn: sqlite3.Connection, persona_id: str, price: float, aggressiveness: float) -> float:
    total = latest_total_value(conn, persona_id)
    cash = get_cash(conn, persona_id)
    target_notional = min(total * MAX_POSITION_WEIGHT * aggressiveness, cash * 0.55)
    return round(max(0.0, target_notional / price), 4)


def choose_buy(conn: sqlite3.Connection, persona_id: str, day: date, persona: str) -> tuple[Candidate | None, float, str]:
    candidates = market_candidates(conn, day)
    held_symbols = {row["symbol"] for row in open_positions(conn, persona_id, day)}
    candidates = [item for item in candidates if item.symbol not in held_symbols and not has_pending_order(conn, persona_id, item.symbol)]
    if not candidates:
        return None, 0.0, "没有合适的新仓位候选。"

    if persona == "quality":
        preferred = {"MSFT", "AAPL", "GOOGL", "AMZN", "COST", "V", "MA", "PG"}
        scored = sorted(
            candidates,
            key=lambda c: ((c.symbol in preferred), -abs(c.day_return), bool(c.ai_tags), c.close),
            reverse=True,
        )
        pick = scored[0]
        limit = pick.close * (0.992 if pick.day_return > 0.01 else 1.002)
        reason = f"质量型组合补充 {pick.symbol}，兼顾大盘稳定性与估值纪律。"
    elif persona == "momentum":
        scored = sorted(candidates, key=lambda c: (bool(c.ai_tags), c.day_return, c.close), reverse=True)
        pick = scored[0]
        limit = pick.close * 1.006
        reason = f"成长动量型追踪强势趋势，{pick.symbol} 今日动量和 AI 相关度较突出。"
    else:
        scored = sorted(candidates, key=lambda c: (bool(c.ai_tags), -c.day_return, c.close), reverse=True)
        pick = scored[0]
        limit = pick.close * 0.985
        reason = f"逆向价值型等待 {pick.symbol} 回落到更舒服的价格再接。"
    return pick, round(limit, 2), reason


def choose_sell(conn: sqlite3.Connection, persona_id: str, day: date, persona: str) -> tuple[dict | None, float, str]:
    positions = open_positions(conn, persona_id, day)
    if not positions:
        return None, 0.0, "没有持仓需要卖出。"

    enriched: list[dict] = []
    for pos in positions:
        pnl = float(pos["close"]) / float(pos["avg_cost"]) - 1
        item = dict(pos)
        item["pnl"] = pnl
        enriched.append(item)

    if persona == "quality":
        candidates = [p for p in enriched if p["pnl"] < -0.08 or p["pnl"] > 0.18]
        if not candidates:
            return None, 0.0, "质量型继续持有核心仓位。"
        pick = sorted(candidates, key=lambda p: abs(p["pnl"]), reverse=True)[0]
        limit = float(pick["close"]) * (0.997 if pick["pnl"] < 0 else 1.015)
        reason = f"质量型对 {pick['symbol']} 做纪律性减仓，当前持仓收益 {pick['pnl'] * 100:+.2f}%。"
    elif persona == "momentum":
        candidates = [p for p in enriched if p["pnl"] < -0.06 or p["pnl"] > 0.22]
        if not candidates:
            return None, 0.0, "动量型继续让趋势运行。"
        pick = sorted(candidates, key=lambda p: p["pnl"])[0]
        limit = float(pick["close"]) * 0.995
        reason = f"成长动量型给 {pick['symbol']} 设置风控卖出计划。"
    else:
        candidates = [p for p in enriched if p["pnl"] > 0.12]
        if not candidates:
            return None, 0.0, "逆向价值型暂不急于卖出。"
        pick = sorted(candidates, key=lambda p: p["pnl"], reverse=True)[0]
        limit = float(pick["close"]) * 1.01
        reason = f"逆向价值型计划在 {pick['symbol']} 反弹后兑现部分修复收益。"
    return pick, round(limit, 2), reason


def generate_orders_for_persona(conn: sqlite3.Connection, persona_id: str, day: date) -> list[int]:
    valid_date = next_business_day(day).isoformat()
    plan_date = day.isoformat()
    created: list[int] = []

    sell, sell_limit, sell_reason = choose_sell(conn, persona_id, day, persona_id)
    if sell:
        qty = round(float(sell["quantity"]) * 0.5, 4)
        if qty > 0:
            created.append(
                place_order(conn, persona_id, sell["symbol"], "SELL", qty, sell_limit, sell_reason, plan_date, valid_date)
            )

    buy, buy_limit, buy_reason = choose_buy(conn, persona_id, day, persona_id)
    if buy:
        aggressiveness = 0.55 if persona_id == "quality" else 0.75 if persona_id == "momentum" else 0.6
        qty = target_quantity(conn, persona_id, buy_limit, aggressiveness)
        if qty > 0:
            created.append(
                place_order(conn, persona_id, buy.symbol, "BUY", qty, buy_limit, buy_reason, plan_date, valid_date)
            )
    return created


def plan_text_for_orders(conn: sqlite3.Connection, order_ids: list[int]) -> str:
    if not order_ids:
        return "今日不新增订单，继续观察现有持仓和 AI 产业链变化。"
    placeholders = ",".join("?" for _ in order_ids)
    lines = []
    for row in rows(conn, f"SELECT * FROM orders WHERE id IN ({placeholders}) ORDER BY id", tuple(order_ids)):
        lines.append(
            f"- {row['side']} {row['symbol']} {row['quantity']:.4f} 股，限价 {row['limit_price']:.2f}，"
            f"有效日 {row['valid_date']}，状态 {row['status']}。{row['reason']}"
        )
    return "\n".join(lines)


def persona_profile(persona_id: str) -> dict[str, str]:
    if persona_id == "quality":
        return {
            "原则": "先保护本金，再用小仓位买入高质量公司。",
            "买入条件": "优先看现金流和商业稳定性；如果当天涨幅过大，就把限价放低一点等回落。",
            "卖出条件": "单仓亏损超过约 8% 或盈利超过约 18% 时，才考虑纪律性减仓。",
            "风险焦点": "避免因为 AI 热点而追高，保留现金，控制单股仓位。",
        }
    if persona_id == "momentum":
        return {
            "原则": "让强者更强，优先跟随 AI 产业链和成长股里的资金趋势。",
            "买入条件": "AI 标签优先，其次看当日相对强度；若趋势强，允许用略高于收盘价的限价追入。",
            "卖出条件": "趋势失败、亏损超过约 6%，或单仓盈利过高需要锁定收益时减仓。",
            "风险焦点": "容易追高，所以用次日限价触发和仓位上限约束冲动。",
        }
    return {
        "原则": "不追强势，专门找大型股或 AI 产业链里被短期抛售的机会。",
        "买入条件": "AI 相关或大盘股出现明显回调时，只在次日继续回落到目标价才买。",
        "卖出条件": "反弹修复后分批兑现，不长期恋战。",
        "风险焦点": "便宜可能有原因，所以只用部分仓位试探，避免越跌越买。",
    }


def order_rows(conn: sqlite3.Connection, order_ids: list[int]) -> list[dict]:
    if not order_ids:
        return []
    placeholders = ",".join("?" for _ in order_ids)
    return rows(conn, f"SELECT * FROM orders WHERE id IN ({placeholders}) ORDER BY id", tuple(order_ids))


def top_market_evidence(conn: sqlite3.Connection, day: date) -> dict[str, list[dict]]:
    candidates = market_candidates(conn, day)
    ai_candidates = [item for item in candidates if item.ai_tags]
    return {
        "strong_ai": [item.__dict__ for item in sorted(ai_candidates, key=lambda item: item.day_return, reverse=True)[:3]],
        "weak_ai": [item.__dict__ for item in sorted(ai_candidates, key=lambda item: item.day_return)[:3]],
        "strong_all": [item.__dict__ for item in sorted(candidates, key=lambda item: item.day_return, reverse=True)[:3]],
        "weak_all": [item.__dict__ for item in sorted(candidates, key=lambda item: item.day_return)[:3]],
    }


def format_evidence(items: list[dict]) -> str:
    if not items:
        return "暂无足够数据"
    return "，".join(f"{item['symbol']} {item['day_return'] * 100:+.2f}%" for item in items)


def persona_analysis(conn: sqlite3.Connection, persona_id: str, day: date, market_summary: str, ai_summary: str) -> str:
    profile = persona_profile(persona_id)
    evidence = top_market_evidence(conn, day)
    positions = open_positions(conn, persona_id, day)
    cash = get_cash(conn, persona_id)
    total = latest_total_value(conn, persona_id)
    position_text = (
        "当前没有持仓，第一优先级是建立第一笔观察仓。"
        if not positions
        else "当前持仓："
        + "，".join(
            f"{row['symbol']} {row['quantity']:.4f} 股，成本 {row['avg_cost']:.2f}，现价 {row['close']:.2f}"
            for row in positions
        )
        + "。"
    )

    if persona_id == "quality":
        interpretation = "指数整体温和时，我不急着追最热股票，而是检查优质名单里有没有价格可接受的标的。"
        candidate_logic = "候选排序偏向 MSFT、AAPL、GOOGL、AMZN、COST、V、MA、PG 这类质量资产；AI 标签只是加分项，不是硬约束。"
    elif persona_id == "momentum":
        interpretation = "我把 AI 产业链强弱当作主线，优先寻找当天还在被资金推高的标的。"
        candidate_logic = "候选排序先看是否属于 AI 产业链，再看当日涨幅；强势标的允许用略高限价等待次日延续。"
    else:
        interpretation = "我不买最强的股票，而是看 AI 产业链和大型股里谁被卖得最狠，等待次日更低价格触发。"
        candidate_logic = "候选排序先看 AI 相关性，再看跌幅；限价通常低于收盘价，买不到也没关系。"

    return "\n".join(
        [
            f"**策略原则**：{profile['原则']}",
            f"**我看到的市场**：{market_summary} {ai_summary}",
            f"**证据清单**：AI 强势：{format_evidence(evidence['strong_ai'])}；AI 回调：{format_evidence(evidence['weak_ai'])}。",
            f"**当前组合**：现金 {cash:,.2f}，估算总资产 {total:,.2f}。{position_text}",
            f"**我的解释**：{interpretation}",
            f"**候选规则**：{candidate_logic}",
            f"**买入规则**：{profile['买入条件']}",
            f"**卖出规则**：{profile['卖出条件']}",
            f"**主要风险**：{profile['风险焦点']}",
        ]
    )


def decision_log_for_orders(conn: sqlite3.Connection, persona_id: str, order_ids: list[int]) -> str:
    profile = persona_profile(persona_id)
    selected = order_rows(conn, order_ids)
    if not selected:
        return "\n".join(
            [
                "**今日行动**：不新增订单。",
                f"**原因**：没有同时满足该人格买入/卖出条件和风控约束的机会。",
                f"**下一步观察**：继续按规则等待：{profile['买入条件']}",
            ]
        )

    lines = ["**今日行动**："]
    for row in selected:
        verb = "买入计划" if row["side"] == "BUY" else "卖出计划"
        lines.extend(
            [
                f"- {verb} {row['symbol']}，数量 {row['quantity']:.4f} 股，限价 {row['limit_price']:.2f}，有效日 {row['valid_date']}。",
                f"  - 触发逻辑：次日开盘或日内区间触及该限价才成交；没有触及就过期。",
                f"  - 选择理由：{row['reason']}",
                f"  - 风控含义：仍受现金、单股仓位、持仓数量和禁止做空规则约束；当前状态 {row['status']}。",
            ]
        )
    return "\n".join(lines)
