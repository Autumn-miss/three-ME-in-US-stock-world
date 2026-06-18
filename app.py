from __future__ import annotations

from html import escape
from pathlib import Path
import re

import pandas as pd
import plotly.express as px
import streamlit as st

from virtual_trader.config import DB_PATH
from virtual_trader.db import (
    connect,
    init_db,
    latest_price_map,
    list_ai_symbols,
    list_orders,
    list_persona_reports,
    list_personas,
    list_positions,
    list_snapshots,
    list_symbols,
    list_trades,
    price_source_summary,
    seed_defaults,
)


st.set_page_config(page_title="Virtual US Stock World", page_icon="📈", layout="wide")

st.markdown(
    """
    <style>
      .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: min(1600px, 96vw);
      }
      div[data-testid="stMetric"] {
        min-width: 0;
      }
      div[data-testid="stMetricValue"] {
        font-size: clamp(2.1rem, 5vw, 3.4rem);
        white-space: nowrap;
      }
      div[data-testid="stMetricLabel"] {
        font-size: clamp(1rem, 2.6vw, 1.25rem);
      }
      .position-card {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 16px;
        margin: 0 0 12px 0;
        background: #ffffff;
      }
      .position-head {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: flex-start;
        margin-bottom: 14px;
      }
      .position-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #262730;
      }
      .position-subtitle {
        margin-top: 4px;
        color: #6b7280;
        font-size: 0.9rem;
      }
      .position-persona {
        color: #374151;
        font-weight: 600;
        white-space: nowrap;
      }
      .position-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(120px, 1fr));
        gap: 12px;
      }
      .position-label {
        color: #8a8d96;
        font-size: 0.82rem;
        margin-bottom: 3px;
      }
      .position-value {
        color: #262730;
        font-size: 1rem;
        font-weight: 650;
      }
      .position-pnl-positive {
        color: #0f8a3b;
      }
      .position-pnl-negative {
        color: #c73a3a;
      }
      .strategy-day {
        border-top: 1px solid #e5e7eb;
        padding: 18px 0 8px 0;
      }
      .strategy-date {
        font-size: 1.35rem;
        font-weight: 750;
        color: #262730;
        margin-bottom: 8px;
      }
      .strategy-persona {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 14px 16px;
        margin: 12px 0;
        background: #ffffff;
      }
      .strategy-persona-title {
        font-weight: 750;
        color: #262730;
        margin-bottom: 8px;
      }
      .strategy-matrix-wrap {
        overflow-x: auto;
        margin: 10px 0 20px 0;
        border: 1px solid #d9dde3;
        border-radius: 8px;
        background: #ffffff;
        width: 100%;
      }
      .strategy-matrix-wrap::-webkit-scrollbar {
        height: 10px;
      }
      .strategy-matrix-wrap::-webkit-scrollbar-thumb {
        background: #c9ced6;
        border-radius: 999px;
      }
      .strategy-matrix {
        border-collapse: collapse;
        min-width: 1040px;
        width: 100%;
        table-layout: fixed;
      }
      .strategy-matrix th,
      .strategy-matrix td {
        border: 1px solid #d9dde3;
        vertical-align: top;
        padding: 10px 12px;
      }
      .strategy-matrix th {
        background: #f6f7f9;
        color: #262730;
        font-size: 1rem;
        font-weight: 750;
        text-align: left;
      }
      .strategy-matrix .row-label {
        width: 124px;
        min-width: 124px;
        background: #fbfbfc;
        color: #262730;
        font-weight: 750;
        position: sticky;
        left: 0;
        z-index: 1;
      }
      .strategy-matrix .day-cell {
        width: 176px;
        min-width: 176px;
        color: #30323d;
        font-size: 0.86rem;
        line-height: 1.42;
        white-space: normal;
        overflow-wrap: anywhere;
      }
      .strategy-matrix .day-date {
        display: block;
        color: #7a7f8c;
        font-size: 0.78rem;
        font-weight: 500;
        margin-top: 3px;
      }
      .strategy-matrix .spacer td {
        background: #f9fafb;
        height: 14px;
        padding: 0;
      }
      @media (max-width: 760px) {
        .position-head {
          display: block;
        }
        .position-persona {
          margin-top: 8px;
        }
        .position-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def table_height(row_count: int, max_rows: int | None = None) -> int:
    visible_rows = row_count if max_rows is None else min(row_count, max_rows)
    return min(38 + max(1, visible_rows) * 35, 900)


PERSONA_NAME_MAP = {
    "稳健质量型": "Quality & Stability",
    "成长动量型": "Growth & Momentum",
    "逆向价值型": "Contrarian Value",
}

PERSONA_STYLE_MAP = {
    "质量与风控": "Quality and Risk Control",
    "成长与趋势": "Growth and Trend",
    "逆向与估值修复": "Contrarian and Valuation Reversion",
}

STRATEGY_ROW_MAP = {
    "策略原则": "Strategy Principle",
    "我看到的市场": "What I See in the Market",
    "证据清单": "Evidence List",
    "当前组合": "Current Portfolio",
    "我的解释": "My Interpretation",
    "候选规则": "Candidate Rules",
    "买入规则": "Buy Rules",
    "卖出规则": "Sell Rules",
    "主要风险": "Key Risks",
    "今日行动": "Today's Plan",
    "行动": "Orders and Executions",
    "复盘": "Review",
}

TRANSLATION_REPLACEMENTS = [
    ("今日市场数据有限，虚拟人主要依据个股价格和风控规则行动。", "Market data is limited today, so the personas rely mainly on single-stock price action and risk rules."),
    ("今日没有到期订单需要复盘。", "No expiring orders require review today."),
    ("今日不新增订单，继续观察现有持仓和 AI 产业链变化。", "No new orders today. Continue watching current holdings and AI-sector developments."),
    ("当前没有持仓，第一优先级是建立第一笔观察仓。", "There are no current positions. The first priority is to open an initial starter position."),
    ("次日开盘或日内区间触及该限价才成交；没有触及就过期。", "The order fills only if the next day's open or intraday range touches the limit price; otherwise it expires."),
    ("仍受现金、单股仓位、持仓数量和禁止做空规则约束；当前状态", "The order still remains subject to cash, single-position size, position-count, and no-shorting limits; current status"),
    ("没有同时满足该人格买入/卖出条件和风控约束的机会。", "No setup met both the persona's buy/sell conditions and its risk constraints."),
    ("继续按规则等待：", "Keep waiting under the rules: "),
    ("主要指数表现：", "Major index moves: "),
    ("AI 产业链强势标的：", "AI leaders: "),
    ("回调标的：", "Pullback names: "),
    ("AI 强势：", "AI leaders: "),
    ("AI 回调：", "AI pullbacks: "),
    ("当前持仓：", "Current positions: "),
    ("现金", "Cash"),
    ("估算总资产", "Estimated total value"),
    ("成本", "cost"),
    ("现价", "last price"),
    ("限价", "limit"),
    ("有效日", "valid on"),
    ("状态", "status"),
    ("已成交", "filled"),
    ("未成交：", "not filled: "),
    ("触发逻辑：", "Execution rule: "),
    ("选择理由：", "Why selected: "),
    ("风控含义：", "Risk control: "),
    ("今日行动", "Today's action"),
    ("原因", "Reason"),
    ("下一步观察", "Next watch item"),
    ("买入计划", "Buy plan"),
    ("卖出计划", "Sell plan"),
    ("买入", "Buy"),
    ("卖出", "Sell"),
    ("股", "shares"),
    ("质量型组合补充", "Quality portfolio adds"),
    ("成长动量型追踪强势趋势", "Growth & Momentum tracks a strong trend in"),
    ("成长动量型给", "Growth & Momentum gives"),
    ("逆向价值型等待", "Contrarian Value waits for"),
    ("逆向价值型计划在", "Contrarian Value plans to"),
    ("当前持仓收益", "current holding return"),
    ("做纪律性减仓", "to trim the position under discipline"),
    ("设置风控卖出计划", "to set a risk-control sell plan"),
    ("回落到更舒服的价格再接。", "to pull back to a more comfortable entry price before buying."),
    ("反弹后兑现部分修复收益。", "to realize part of the rebound recovery gain."),
    ("次日回落和 AI 相关度较突出。", "for a next-day pullback with strong AI relevance."),
    ("持仓数量超过上限。", "Position count exceeds the limit."),
    ("次日日内价格没有触及计划价，订单当日失效。", "The next day's intraday price never touched the planned price, so the order expired."),
    ("触发时现金不足，规则层拒绝成交。", "Cash was insufficient at trigger time, so the execution was rejected by the rules."),
    ("触发时持仓不足，禁止做空。", "Holdings were insufficient at trigger time; short selling is not allowed."),
    ("现金不足，规则层拒绝买入。", "Cash is insufficient, so the buy was rejected by the rules."),
    ("单股计划仓位超过上限。", "The planned single-stock position exceeds the limit."),
    ("买入后现金低于最低保留比例。", "Cash would fall below the minimum reserve ratio after the buy."),
    ("卖出数量超过当前持仓，禁止做空。", "Sell quantity exceeds the current position; short selling is not allowed."),
]


def translate_chinese_text(text: object) -> str:
    source = str(text or "").strip()
    if not source:
        return "-"

    translated = source
    for original, replacement in TRANSLATION_REPLACEMENTS:
        translated = translated.replace(original, replacement)

    translated = re.sub(r"\bBUY\b", "Buy", translated)
    translated = re.sub(r"\bSELL\b", "Sell", translated)
    translated = re.sub(r"\bPENDING\b", "Pending", translated)
    translated = re.sub(r"\bFILLED\b", "Filled", translated)
    translated = re.sub(r"\bREJECTED\b", "Rejected", translated)
    translated = re.sub(r"\bEXPIRED\b", "Expired", translated)
    translated = translated.replace("，", ", ").replace("。", ". ").replace("；", "; ").replace("：", ": ")
    translated = translated.replace("（", "(").replace("）", ")")
    translated = re.sub(r"\s+", " ", translated).strip()
    return translated


def bilingual_plain_text(value: object) -> str:
    if pd.isna(value):
        return "-"
    original = str(value or "").strip()
    if not original:
        return "-"
    return f"EN: {translate_chinese_text(original)}\nZH: {original}"


def bilingual_html_text(value: object) -> str:
    if pd.isna(value):
        return "-"
    original = str(value or "").strip()
    if not original:
        return "-"
    english = translate_chinese_text(original)
    return (
        f"<strong>EN:</strong> {escape(english).replace(chr(10), '<br>')}"
        "<br>"
        f"<strong>ZH:</strong> {escape(original).replace(chr(10), '<br>')}"
    )

POSITION_COLUMNS = ["Persona", "Ticker", "Company (Sector)", "AI Tags", "Total Shares", "Cost Basis", "Last Price", "Market Value", "Unrealized P&L"]


def build_position_view(positions_df: pd.DataFrame, personas_df: pd.DataFrame, symbols_df: pd.DataFrame) -> pd.DataFrame:
    if positions_df.empty:
        return pd.DataFrame(columns=POSITION_COLUMNS)

    source = positions_df.copy()
    metadata = symbols_df[["symbol", "name", "sector", "ai_tags"]].rename(
        columns={"name": "company_name", "sector": "symbol_sector", "ai_tags": "symbol_ai_tags"}
    )
    source = source.merge(metadata, on="symbol", how="left")
    source["company_name"] = source.get("company_name", pd.Series(index=source.index, dtype="object")).fillna(
        source["symbol"].map(metadata.set_index("symbol")["company_name"])
    )
    source["sector"] = source.get("sector", pd.Series(index=source.index, dtype="object")).fillna(source["symbol_sector"])
    source["ai_tags"] = source.get("ai_tags", pd.Series(index=source.index, dtype="object")).fillna(source["symbol_ai_tags"])

    view = source.merge(personas_df, left_on="persona_id", right_on="id", how="left").rename(
        columns={
            "name": "Persona",
            "symbol": "Ticker",
            "company_name": "Company Name",
            "sector": "Sector",
            "quantity": "Shares",
            "avg_cost": "Average Cost",
            "last_price": "Last Price",
            "market_value": "Market Value",
            "unrealized_pnl": "Unrealized P&L",
            "ai_tags": "AI Tags",
        }
    )
    for column in POSITION_COLUMNS:
        if column not in view.columns:
            view[column] = ""
    view["Company (Sector)"] = view.apply(
        lambda row: f"{row['Company Name']} ({row['Sector']})" if row["Sector"] else row["Company Name"],
        axis=1,
    )
    view["Total Shares"] = view["Shares"]
    view["Cost Basis"] = view["Average Cost"]
    view["Last Price"] = view["Last Price"]
    return view[POSITION_COLUMNS]


def money(value: object) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "-"


def quantity(value: object) -> str:
    try:
        return f"{float(value):,.4f}"
    except (TypeError, ValueError):
        return "-"


def render_position_cards(position_view: pd.DataFrame) -> None:
    for _, row in position_view.iterrows():
        data = row.to_dict()
        pnl_value = float(data.get("Unrealized P&L") or 0)
        pnl_class = "position-pnl-positive" if pnl_value >= 0 else "position-pnl-negative"
        ai_tags = data.get("AI Tags") or "No AI tags"
        st.markdown(
            f"""
            <div class="position-card">
              <div class="position-head">
                <div>
                  <div class="position-title">{escape(str(data["Ticker"]))} · {escape(str(data["Company (Sector)"]))}</div>
                  <div class="position-subtitle">{escape(str(ai_tags))}</div>
                </div>
                <div class="position-persona">{escape(str(data["Persona"]))}</div>
              </div>
              <div class="position-grid">
                <div>
                  <div class="position-label">Total Shares</div>
                  <div class="position-value">{quantity(data["Total Shares"])}</div>
                </div>
                <div>
                  <div class="position-label">Cost Basis</div>
                  <div class="position-value">{money(data["Cost Basis"])}</div>
                </div>
                <div>
                  <div class="position-label">Last Price</div>
                  <div class="position-value">{money(data["Last Price"])}</div>
                </div>
                <div>
                  <div class="position-label">Market Value</div>
                  <div class="position-value">{money(data["Market Value"])}</div>
                </div>
                <div>
                  <div class="position-label">Unrealized P&amp;L</div>
                  <div class="position-value {pnl_class}">{money(data["Unrealized P&L"])}</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def build_position_ledger(
    trades_df: pd.DataFrame,
    personas_df: pd.DataFrame,
    symbols_df: pd.DataFrame,
    latest_prices: dict[str, float],
) -> tuple[pd.DataFrame, dict[tuple[str, str], pd.DataFrame]]:
    summary_columns = [
        "persona_id",
        "symbol",
        "Persona",
        "Company (Sector)",
        "Total Shares",
        "Cost Basis",
        "Last Price",
        "Position Value",
        "Realized P&L",
        "Unrealized P&L",
        "Total P&L",
        "Trade Count",
    ]
    if trades_df.empty:
        return pd.DataFrame(columns=summary_columns), {}

    persona_names = personas_df.set_index("id")["name"].to_dict()
    symbol_meta = symbols_df.set_index("symbol")[["name", "sector", "ai_tags"]].to_dict("index")
    summaries: list[dict[str, object]] = []
    histories: dict[tuple[str, str], pd.DataFrame] = {}

    sorted_trades = trades_df.sort_values(["persona_id", "symbol", "trade_date", "id"])
    for (persona_id, symbol), group in sorted_trades.groupby(["persona_id", "symbol"], sort=True):
        held_quantity = 0.0
        avg_cost = 0.0
        realized_pnl = 0.0
        history_rows: list[dict[str, object]] = []

        for _, trade in group.iterrows():
            quantity_value = float(trade["quantity"])
            price_value = float(trade["price"])
            amount_value = float(trade["amount"])
            if trade["side"] == "BUY":
                new_quantity = held_quantity + quantity_value
                avg_cost = ((held_quantity * avg_cost) + amount_value) / new_quantity if new_quantity else 0.0
                held_quantity = new_quantity
            else:
                realized_pnl += amount_value - (avg_cost * quantity_value)
                held_quantity = max(0.0, held_quantity - quantity_value)
                if held_quantity <= 0.000001:
                    held_quantity = 0.0
                    avg_cost = 0.0

            history_rows.append(
                {
                    "Trade Date": trade["trade_date"],
                    "Side": "Buy" if trade["side"] == "BUY" else "Sell",
                    "Shares": quantity_value,
                    "Price": price_value,
                    "Amount": amount_value,
                    "Shares After Trade": held_quantity,
                    "Cost Basis After Trade": avg_cost if held_quantity else 0.0,
                    "Reason": trade["reason"],
                }
            )

        meta = symbol_meta.get(symbol, {"name": symbol, "sector": "", "ai_tags": ""})
        company = f"{meta['name']} ({meta['sector']})" if meta.get("sector") else meta["name"]
        last_price = float(latest_prices.get(symbol, avg_cost or 0.0))
        market_value = held_quantity * last_price
        unrealized_pnl = held_quantity * (last_price - avg_cost)
        total_pnl = realized_pnl + unrealized_pnl
        key = (str(persona_id), str(symbol))

        summaries.append(
            {
                "persona_id": persona_id,
                "symbol": symbol,
                "Persona": persona_names.get(persona_id, persona_id),
                "Company (Sector)": company,
                "Total Shares": held_quantity,
                "Cost Basis": avg_cost,
                "Last Price": last_price,
                "Position Value": market_value,
                "Realized P&L": realized_pnl,
                "Unrealized P&L": unrealized_pnl,
                "Total P&L": total_pnl,
                "Trade Count": len(history_rows),
            }
        )
        histories[key] = pd.DataFrame(history_rows)

    return pd.DataFrame(summaries, columns=summary_columns), histories


def render_position_ledger(summary_df: pd.DataFrame, histories: dict[tuple[str, str], pd.DataFrame]) -> None:
    if summary_df.empty:
        st.info("No executed trades yet.")
        return

    for _, row in summary_df.sort_values(["Persona", "symbol"]).iterrows():
        pnl_class = "position-pnl-positive" if float(row["Total P&L"]) >= 0 else "position-pnl-negative"
        title = f"{row['Persona']} · {row['symbol']} · {row['Company (Sector)']}"
        with st.expander(title, expanded=True):
            st.markdown(
                f"""
                <div class="position-card">
                  <div class="position-grid">
                    <div>
                      <div class="position-label">Total Shares</div>
                      <div class="position-value">{quantity(row["Total Shares"])}</div>
                    </div>
                    <div>
                      <div class="position-label">Cost Basis</div>
                      <div class="position-value">{money(row["Cost Basis"])}</div>
                    </div>
                    <div>
                      <div class="position-label">Last Price</div>
                      <div class="position-value">{money(row["Last Price"])}</div>
                    </div>
                    <div>
                      <div class="position-label">Position Value</div>
                      <div class="position-value">{money(row["Position Value"])}</div>
                    </div>
                    <div>
                      <div class="position-label">Total P&amp;L</div>
                      <div class="position-value {pnl_class}">{money(row["Total P&L"])}</div>
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.dataframe(
                histories[(row["persona_id"], row["symbol"])],
                width="stretch",
                hide_index=True,
                column_config={
                    "Shares": st.column_config.NumberColumn(format="%.4f"),
                    "Price": st.column_config.NumberColumn(format="$%.2f"),
                    "Amount": st.column_config.NumberColumn(format="$%.2f"),
                    "Shares After Trade": st.column_config.NumberColumn(format="%.4f"),
                    "Cost Basis After Trade": st.column_config.NumberColumn(format="$%.2f"),
                },
            )


def action_text_for_date(persona_id: str, day: str, orders_df: pd.DataFrame, trades_df: pd.DataFrame) -> str:
    lines: list[str] = []
    if not trades_df.empty:
        day_trades = trades_df[(trades_df["persona_id"] == persona_id) & (trades_df["trade_date"] == day)]
        for _, trade in day_trades.iterrows():
            side = "买入" if trade["side"] == "BUY" else "卖出"
            lines.append(f"- 已成交：{side} {trade['symbol']} {float(trade['quantity']):.4f} 股，价格 {float(trade['price']):.2f}。")
    if not orders_df.empty:
        day_orders = orders_df[(orders_df["persona_id"] == persona_id) & (orders_df["plan_date"] == day)]
        for _, order in day_orders.iterrows():
            side = "买入" if order["side"] == "BUY" else "卖出"
            status = order["status"]
            lines.append(
                f"- 计划订单：{side} {order['symbol']} {float(order['quantity']):.4f} 股，限价 {float(order['limit_price']):.2f}，状态 {status}。"
            )
    return "\n".join(lines) if lines else "- 当日没有成交或新增订单。"


STRATEGY_ROWS = [
    "策略原则",
    "我看到的市场",
    "证据清单",
    "当前组合",
    "我的解释",
    "候选规则",
    "买入规则",
    "卖出规则",
    "主要风险",
    "",
    "今日行动",
    "行动",
    "复盘",
]


def parse_strategy_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_label: str | None = None
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("**") and "**" in line[2:]:
            end = line.find("**", 2)
            label = line[2:end]
            value = line[end + 2 :].lstrip("：: ").strip()
            current_label = label
            sections[label] = value
        elif current_label:
            sections[current_label] = f"{sections[current_label]}<br>{escape(line)}" if sections[current_label] else escape(line)
    return sections


def html_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    escaped = escape(text)
    escaped = escaped.replace("\n", "<br>")
    return escaped


def day_heading(index: int, report_date: str) -> str:
    names = ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5"]
    label = names[index] if index < len(names) else f"Day {index + 1}"
    date_label = escape(report_date) if report_date else "Waiting"
    return f"{label}<span class=\"day-date\">{date_label}</span>"


def five_day_window(report_dates: list[str]) -> list[str]:
    window = list(report_dates[-5:])
    while len(window) < 5:
        window.append("")
    return window


def historical_windows(dates_desc: list[str], window_size: int = 5) -> list[list[str]]:
    windows: list[list[str]] = []
    for start in range(window_size, len(dates_desc), window_size):
        window = sorted(dates_desc[start : start + window_size])
        if window:
            windows.append(window)
    return windows


def strategy_cell(
    persona_id: str,
    report_date: str,
    label: str,
    report_row: pd.Series | None,
    orders_df: pd.DataFrame,
    trades_df: pd.DataFrame,
) -> str:
    if report_row is None:
        return "-"
    sections = parse_strategy_sections(str(report_row["analysis"]))
    if label == "我看到的市场":
        return bilingual_html_text(report_row["market_summary"])
    if label == "今日行动":
        return bilingual_html_text(report_row["plan_text"])
    if label == "行动":
        return bilingual_html_text(action_text_for_date(persona_id, report_date, orders_df, trades_df))
    if label == "复盘":
        return bilingual_html_text(report_row["review"])
    return bilingual_html_text(sections.get(label, ""))


def render_strategy_matrix(
    persona: pd.Series,
    report_dates: list[str],
    reports_df: pd.DataFrame,
    orders_df: pd.DataFrame,
    trades_df: pd.DataFrame,
) -> None:
    persona_reports = reports_df[reports_df["persona_id"] == persona["id"]].set_index("date")
    report_dates = five_day_window(report_dates)
    headers = "".join(f"<th>{day_heading(index, report_date)}</th>" for index, report_date in enumerate(report_dates))
    body_rows: list[str] = []
    for label in STRATEGY_ROWS:
        if label == "":
            body_rows.append(f"<tr class=\"spacer\"><td class=\"row-label\"></td><td colspan=\"{len(report_dates)}\"></td></tr>")
            continue
        cells: list[str] = []
        for report_date in report_dates:
            report_row = persona_reports.loc[report_date] if report_date in persona_reports.index else None
            cells.append(
                "<td class=\"day-cell\">"
                + strategy_cell(str(persona["id"]), report_date, label, report_row, orders_df, trades_df)
                + "</td>"
            )
        body_rows.append(f"<tr><td class=\"row-label\">{escape(STRATEGY_ROW_MAP.get(label, label))}</td>{''.join(cells)}</tr>")

    table_html = (
        '<div class="strategy-matrix-wrap">'
        '<table class="strategy-matrix">'
        f"<thead><tr><th class=\"row-label\"></th>{headers}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
    )
    st.markdown(f"### {persona['name']} · {persona['style']}")
    st.markdown(table_html, unsafe_allow_html=True)


@st.cache_data(ttl=30)
def load_data(db_path: str):
    with connect(Path(db_path)) as conn:
        init_db(conn)
        if not list_personas(conn):
            seed_defaults(conn)
        return {
            "personas": list_personas(conn),
            "symbols": list_symbols(conn),
            "positions": list_positions(conn),
            "snapshots": list_snapshots(conn),
            "orders": list_orders(conn),
            "trades": list_trades(conn),
            "reports": list_persona_reports(conn),
            "ai_symbols": list_ai_symbols(conn),
            "prices": latest_price_map(conn),
            "price_sources": price_source_summary(conn),
        }


data = load_data(str(DB_PATH))
personas = pd.DataFrame(data["personas"])
if not personas.empty:
    personas["name"] = personas["name"].map(lambda value: PERSONA_NAME_MAP.get(str(value), str(value)))
    personas["style"] = personas["style"].map(lambda value: PERSONA_STYLE_MAP.get(str(value), str(value)))
symbols = pd.DataFrame(data["symbols"])
positions = pd.DataFrame(data["positions"])
snapshots = pd.DataFrame(data["snapshots"])
orders = pd.DataFrame(data["orders"])
trades = pd.DataFrame(data["trades"])
reports = pd.DataFrame(data["reports"])
ai_symbols = pd.DataFrame(data["ai_symbols"])
price_sources = pd.DataFrame(data["price_sources"])
latest_prices = data["prices"]

st.title("Virtual US Stock World")
st.caption("Three simulated investors, each starting with USD 20,000. Virtual trading only, for observation and research.")

if not price_sources.empty:
    sources = ", ".join(
        f"{row.source} ({row.first_date} to {row.last_date}, {row.rows} rows)" for row in price_sources.itertuples()
    )
    if any(str(source).startswith("synthetic") for source in price_sources["source"]):
        st.error(
            f"The current database includes synthetic demo prices: {sources}. "
            "Run `python3 run_daily.py --reset --demo-days 2` to rebuild with real market data."
        )
    else:
        st.caption(f"Market data source: {sources}")

if snapshots.empty:
    st.info("No portfolio snapshots yet. Run `python3 run_daily.py --demo-days 8` to generate demo data first.")
    st.stop()

latest_date = snapshots["date"].max()
latest = snapshots[snapshots["date"] == latest_date].merge(
    personas, left_on="persona_id", right_on="id", suffixes=("", "_persona")
)

cols = st.columns(3)
for idx, row in latest.sort_values("total_value", ascending=False).reset_index(drop=True).iterrows():
    with cols[idx % 3]:
        st.metric(
            row["name"],
            f"${row['total_value']:,.2f}",
            f"{row['cumulative_return'] * 100:.2f}%",
        )
        st.caption(f"Cash ${row['cash']:,.2f} · Drawdown {row['drawdown'] * 100:.2f}%")

tabs = st.tabs(["Overview", "Returns", "Holdings", "Orders & Trades", "AI Watchlist", "Strategy"])

with tabs[0]:
    st.subheader(f"{latest_date} Rankings")
    ranking = latest[
        ["name", "style", "cash", "positions_value", "total_value", "cumulative_return", "drawdown"]
    ].sort_values("total_value", ascending=False)
    ranking["Return"] = (ranking["cumulative_return"] * 100).map(lambda v: f"{v:.2f}%")
    ranking["Drawdown"] = (ranking["drawdown"] * 100).map(lambda v: f"{v:.2f}%")
    st.dataframe(
        ranking.rename(
            columns={
                "name": "Persona",
                "style": "Style",
                "cash": "Cash",
                "positions_value": "Positions Value",
                "total_value": "Total Value",
            }
        )[["Persona", "Style", "Cash", "Positions Value", "Total Value", "Return", "Drawdown"]],
        width="stretch",
        hide_index=True,
    )

with tabs[1]:
    chart_data = snapshots.merge(personas, left_on="persona_id", right_on="id", suffixes=("", "_persona"))
    st.plotly_chart(
        px.line(chart_data, x="date", y="total_value", color="name", markers=True, title="Portfolio Value"),
        width="stretch",
    )
    st.plotly_chart(
        px.line(chart_data, x="date", y="cumulative_return", color="name", markers=True, title="Cumulative Return"),
        width="stretch",
    )

with tabs[2]:
    if trades.empty:
        st.info("No executed trades yet.")
    else:
        ledger, trade_histories = build_position_ledger(trades, personas, symbols, latest_prices)
        render_position_ledger(ledger, trade_histories)

with tabs[3]:
    st.subheader("Orders")
    if orders.empty:
        st.info("No orders yet.")
    else:
        order_view = orders.merge(personas, left_on="persona_id", right_on="id")
        order_view["reason"] = order_view["reason"].map(bilingual_plain_text)
        order_view["miss_reason"] = order_view["miss_reason"].map(bilingual_plain_text)
        st.dataframe(
            order_view.rename(
                columns={
                    "name": "Persona",
                    "symbol": "Ticker",
                    "side": "Side",
                    "quantity": "Shares",
                    "limit_price": "Limit Price",
                    "status": "Status",
                    "plan_date": "Plan Date",
                    "valid_date": "Valid Date",
                    "execution_price": "Execution Price",
                    "miss_reason": "Miss Reason",
                    "reason": "Reason",
                }
            )[
                ["Plan Date", "Valid Date", "Persona", "Ticker", "Side", "Shares", "Limit Price", "Status", "Execution Price", "Miss Reason", "Reason"]
            ],
            width="stretch",
            hide_index=True,
        )
    st.subheader("Trades")
    if trades.empty:
        st.info("No trades yet.")
    else:
        trade_view = trades.merge(personas, left_on="persona_id", right_on="id")
        trade_view["reason"] = trade_view["reason"].map(bilingual_plain_text)
        st.dataframe(
            trade_view.rename(
                columns={
                    "trade_date": "Trade Date",
                    "name": "Persona",
                    "symbol": "Ticker",
                    "side": "Side",
                    "quantity": "Shares",
                    "price": "Price",
                    "amount": "Amount",
                    "reason": "Reason",
                }
            )[["Trade Date", "Persona", "Ticker", "Side", "Shares", "Price", "Amount", "Reason"]],
            width="stretch",
            hide_index=True,
        )

with tabs[4]:
    st.subheader("AI Watchlist")
    ai_symbol_view = ai_symbols.rename(
        columns={"symbol": "Ticker", "name": "Company", "sector": "Sector", "ai_tags": "AI Tags"}
    )[["Ticker", "Company", "Sector", "AI Tags"]]
    st.dataframe(
        ai_symbol_view,
        width="stretch",
        height=table_height(len(ai_symbol_view)),
        hide_index=True,
        column_config={
            "Ticker": st.column_config.TextColumn(width="small"),
            "Company": st.column_config.TextColumn(width="medium"),
            "Sector": st.column_config.TextColumn(width="medium"),
            "AI Tags": st.column_config.TextColumn(width="large"),
        },
    )
    if not positions.empty:
        ai_positions = positions[positions["ai_tags"].fillna("") != ""]
        if ai_positions.empty:
            st.info("None of the three personas currently holds AI-tagged positions.")
        else:
            st.subheader("AI Holdings")
            ai_position_view = build_position_view(ai_positions, personas, symbols)
            render_position_cards(ai_position_view)

with tabs[5]:
    if reports.empty:
        st.info("No daily reports yet.")
    else:
        dates_desc = sorted(reports["date"].unique(), reverse=True)
        latest_report_date = dates_desc[0]
        recent_dates = sorted(dates_desc[:5])
        older_date_windows = historical_windows(dates_desc)
        st.subheader("Latest 5 Trading Days")
        st.caption(
            f"Strategy coverage is updated through {latest_report_date}. "
            "The dashboard highlights the latest 5 generated trading days by default, "
            "while older strategy history stays collapsed into 5-day windows."
        )
        for _, persona in personas.iterrows():
            render_strategy_matrix(persona, recent_dates, reports, orders, trades)
        if older_date_windows:
            with st.expander("Historical Strategy Windows", expanded=False):
                for history_dates in older_date_windows:
                    start_date = history_dates[0]
                    end_date = history_dates[-1]
                    with st.expander(f"{start_date} to {end_date}", expanded=False):
                        for _, persona in personas.iterrows():
                            render_strategy_matrix(persona, history_dates, reports, orders, trades)
