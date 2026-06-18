from __future__ import annotations

from datetime import date


def build_market_summary(index_moves: dict[str, float]) -> str:
    if not index_moves:
        return "今日市场数据有限，虚拟人主要依据个股价格和风控规则行动。"
    parts = [f"{symbol} {move * 100:+.2f}%" for symbol, move in sorted(index_moves.items())]
    return "主要指数表现：" + "，".join(parts) + "。"


def build_ai_summary(day: date, ai_movers: list[dict]) -> str:
    if not ai_movers:
        return f"{day.isoformat()} AI 产业链暂无足够价格数据，保持观察。"
    leaders = sorted(ai_movers, key=lambda item: item["return"], reverse=True)[:3]
    laggards = sorted(ai_movers, key=lambda item: item["return"])[:3]
    leader_text = "，".join(f"{item['symbol']} {item['return'] * 100:+.2f}%" for item in leaders)
    laggard_text = "，".join(f"{item['symbol']} {item['return'] * 100:+.2f}%" for item in laggards)
    return f"AI 产业链强势标的：{leader_text}。回调标的：{laggard_text}。"
