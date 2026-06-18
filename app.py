from __future__ import annotations

from html import escape
from pathlib import Path

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


st.set_page_config(page_title="虚拟美股投资世界", page_icon="📈", layout="wide")

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


POSITION_COLUMNS = ["虚拟人", "股票", "公司（行业）", "AI 标签", "累计持股数量", "成本", "现价", "市值", "浮盈亏"]


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
            "name": "虚拟人",
            "symbol": "股票",
            "company_name": "公司全名",
            "sector": "行业",
            "quantity": "股数",
            "avg_cost": "平均成本",
            "last_price": "最新价",
            "market_value": "市值",
            "unrealized_pnl": "浮盈亏",
            "ai_tags": "AI 标签",
        }
    )
    for column in POSITION_COLUMNS:
        if column not in view.columns:
            view[column] = ""
    view["公司（行业）"] = view.apply(
        lambda row: f"{row['公司全名']}（{row['行业']}）" if row["行业"] else row["公司全名"],
        axis=1,
    )
    view["累计持股数量"] = view["股数"]
    view["成本"] = view["平均成本"]
    view["现价"] = view["最新价"]
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
        pnl_value = float(data.get("浮盈亏") or 0)
        pnl_class = "position-pnl-positive" if pnl_value >= 0 else "position-pnl-negative"
        ai_tags = data.get("AI 标签") or "非 AI 标签股"
        st.markdown(
            f"""
            <div class="position-card">
              <div class="position-head">
                <div>
                  <div class="position-title">{escape(str(data["股票"]))} · {escape(str(data["公司（行业）"]))}</div>
                  <div class="position-subtitle">{escape(str(ai_tags))}</div>
                </div>
                <div class="position-persona">{escape(str(data["虚拟人"]))}</div>
              </div>
              <div class="position-grid">
                <div>
                  <div class="position-label">累计持股数量</div>
                  <div class="position-value">{quantity(data["累计持股数量"])}</div>
                </div>
                <div>
                  <div class="position-label">成本</div>
                  <div class="position-value">{money(data["成本"])}</div>
                </div>
                <div>
                  <div class="position-label">现价</div>
                  <div class="position-value">{money(data["现价"])}</div>
                </div>
                <div>
                  <div class="position-label">市值</div>
                  <div class="position-value">{money(data["市值"])}</div>
                </div>
                <div>
                  <div class="position-label">浮盈亏</div>
                  <div class="position-value {pnl_class}">{money(data["浮盈亏"])}</div>
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
        "虚拟人",
        "公司（行业）",
        "总持股数量",
        "成本",
        "现价",
        "持仓市值",
        "已实现盈利",
        "未实现盈利",
        "总盈利",
        "交易次数",
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
                    "交易日": trade["trade_date"],
                    "方向": "买入" if trade["side"] == "BUY" else "卖出",
                    "数量": quantity_value,
                    "价格": price_value,
                    "金额": amount_value,
                    "交易后持股": held_quantity,
                    "交易后成本": avg_cost if held_quantity else 0.0,
                    "理由": trade["reason"],
                }
            )

        meta = symbol_meta.get(symbol, {"name": symbol, "sector": "", "ai_tags": ""})
        company = f"{meta['name']}（{meta['sector']}）" if meta.get("sector") else meta["name"]
        last_price = float(latest_prices.get(symbol, avg_cost or 0.0))
        market_value = held_quantity * last_price
        unrealized_pnl = held_quantity * (last_price - avg_cost)
        total_pnl = realized_pnl + unrealized_pnl
        key = (str(persona_id), str(symbol))

        summaries.append(
            {
                "persona_id": persona_id,
                "symbol": symbol,
                "虚拟人": persona_names.get(persona_id, persona_id),
                "公司（行业）": company,
                "总持股数量": held_quantity,
                "成本": avg_cost,
                "现价": last_price,
                "持仓市值": market_value,
                "已实现盈利": realized_pnl,
                "未实现盈利": unrealized_pnl,
                "总盈利": total_pnl,
                "交易次数": len(history_rows),
            }
        )
        histories[key] = pd.DataFrame(history_rows)

    return pd.DataFrame(summaries, columns=summary_columns), histories


def render_position_ledger(summary_df: pd.DataFrame, histories: dict[tuple[str, str], pd.DataFrame]) -> None:
    if summary_df.empty:
        st.info("暂无成交记录。")
        return

    for _, row in summary_df.sort_values(["虚拟人", "symbol"]).iterrows():
        pnl_class = "position-pnl-positive" if float(row["总盈利"]) >= 0 else "position-pnl-negative"
        title = f"{row['虚拟人']} · {row['symbol']} · {row['公司（行业）']}"
        with st.expander(title, expanded=True):
            st.markdown(
                f"""
                <div class="position-card">
                  <div class="position-grid">
                    <div>
                      <div class="position-label">总持股数量</div>
                      <div class="position-value">{quantity(row["总持股数量"])}</div>
                    </div>
                    <div>
                      <div class="position-label">成本</div>
                      <div class="position-value">{money(row["成本"])}</div>
                    </div>
                    <div>
                      <div class="position-label">现价</div>
                      <div class="position-value">{money(row["现价"])}</div>
                    </div>
                    <div>
                      <div class="position-label">持仓市值</div>
                      <div class="position-value">{money(row["持仓市值"])}</div>
                    </div>
                    <div>
                      <div class="position-label">总盈利</div>
                      <div class="position-value {pnl_class}">{money(row["总盈利"])}</div>
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
                    "数量": st.column_config.NumberColumn(format="%.4f"),
                    "价格": st.column_config.NumberColumn(format="$%.2f"),
                    "金额": st.column_config.NumberColumn(format="$%.2f"),
                    "交易后持股": st.column_config.NumberColumn(format="%.4f"),
                    "交易后成本": st.column_config.NumberColumn(format="$%.2f"),
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
    names = ["第一交易日", "第二交易日", "第三交易日", "第四交易日", "第五交易日"]
    label = names[index] if index < len(names) else f"第{index + 1}交易日"
    date_label = escape(report_date) if report_date else "等待生成"
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
        return html_text(report_row["market_summary"])
    if label == "今日行动":
        return html_text(report_row["plan_text"])
    if label == "行动":
        return html_text(action_text_for_date(persona_id, report_date, orders_df, trades_df))
    if label == "复盘":
        return html_text(report_row["review"])
    return html_text(sections.get(label, ""))


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
        body_rows.append(f"<tr><td class=\"row-label\">{escape(label)}</td>{''.join(cells)}</tr>")

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
symbols = pd.DataFrame(data["symbols"])
positions = pd.DataFrame(data["positions"])
snapshots = pd.DataFrame(data["snapshots"])
orders = pd.DataFrame(data["orders"])
trades = pd.DataFrame(data["trades"])
reports = pd.DataFrame(data["reports"])
ai_symbols = pd.DataFrame(data["ai_symbols"])
price_sources = pd.DataFrame(data["price_sources"])
latest_prices = data["prices"]

st.title("虚拟美股投资世界")
st.caption("3 个虚拟投资人，各自 20,000 美元本金。纯虚拟交易，仅用于观察和研究。")

if not price_sources.empty:
    sources = ", ".join(
        f"{row.source} ({row.first_date} 至 {row.last_date}, {row.rows} 条)" for row in price_sources.itertuples()
    )
    if any(str(source).startswith("synthetic") for source in price_sources["source"]):
        st.error(f"当前数据库含演示合成行情：{sources}。请运行 `python3 run_daily.py --reset --demo-days 2` 重新拉取真实行情。")
    else:
        st.caption(f"行情来源：{sources}")

if snapshots.empty:
    st.info("还没有资产快照。先运行 `python3 run_daily.py --demo-days 8` 生成演示数据。")
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
        st.caption(f"现金 ${row['cash']:,.2f} · 回撤 {row['drawdown'] * 100:.2f}%")

tabs = st.tabs(["总览", "收益曲线", "持仓", "订单与交易", "AI 产业链", "投资策略"])

with tabs[0]:
    st.subheader(f"{latest_date} 排名")
    ranking = latest[
        ["name", "style", "cash", "positions_value", "total_value", "cumulative_return", "drawdown"]
    ].sort_values("total_value", ascending=False)
    ranking["收益率"] = (ranking["cumulative_return"] * 100).map(lambda v: f"{v:.2f}%")
    ranking["回撤"] = (ranking["drawdown"] * 100).map(lambda v: f"{v:.2f}%")
    st.dataframe(
        ranking.rename(
            columns={
                "name": "虚拟人",
                "style": "风格",
                "cash": "现金",
                "positions_value": "持仓市值",
                "total_value": "总资产",
            }
        )[["虚拟人", "风格", "现金", "持仓市值", "总资产", "收益率", "回撤"]],
        width="stretch",
        hide_index=True,
    )

with tabs[1]:
    chart_data = snapshots.merge(personas, left_on="persona_id", right_on="id", suffixes=("", "_persona"))
    st.plotly_chart(
        px.line(chart_data, x="date", y="total_value", color="name", markers=True, title="资产净值"),
        width="stretch",
    )
    st.plotly_chart(
        px.line(chart_data, x="date", y="cumulative_return", color="name", markers=True, title="累计收益率"),
        width="stretch",
    )

with tabs[2]:
    if trades.empty:
        st.info("暂无成交记录。")
    else:
        ledger, trade_histories = build_position_ledger(trades, personas, symbols, latest_prices)
        render_position_ledger(ledger, trade_histories)

with tabs[3]:
    st.subheader("订单")
    if orders.empty:
        st.info("暂无订单。")
    else:
        order_view = orders.merge(personas, left_on="persona_id", right_on="id")
        st.dataframe(
            order_view.rename(
                columns={
                    "name": "虚拟人",
                    "symbol": "股票",
                    "side": "方向",
                    "quantity": "股数",
                    "limit_price": "计划价",
                    "status": "状态",
                    "plan_date": "计划日",
                    "valid_date": "有效日",
                    "execution_price": "成交价",
                    "miss_reason": "未成交原因",
                    "reason": "理由",
                }
            )[
                ["计划日", "有效日", "虚拟人", "股票", "方向", "股数", "计划价", "状态", "成交价", "未成交原因", "理由"]
            ],
            width="stretch",
            hide_index=True,
        )
    st.subheader("成交")
    if trades.empty:
        st.info("暂无成交。")
    else:
        trade_view = trades.merge(personas, left_on="persona_id", right_on="id")
        st.dataframe(
            trade_view.rename(
                columns={
                    "trade_date": "成交日",
                    "name": "虚拟人",
                    "symbol": "股票",
                    "side": "方向",
                    "quantity": "股数",
                    "price": "价格",
                    "amount": "金额",
                    "reason": "理由",
                }
            )[["成交日", "虚拟人", "股票", "方向", "股数", "价格", "金额", "理由"]],
            width="stretch",
            hide_index=True,
        )

with tabs[4]:
    st.subheader("AI 产业链股票池")
    ai_symbol_view = ai_symbols.rename(
        columns={"symbol": "股票", "name": "公司", "sector": "板块", "ai_tags": "AI 标签"}
    )[["股票", "公司", "板块", "AI 标签"]]
    st.dataframe(
        ai_symbol_view,
        width="stretch",
        height=table_height(len(ai_symbol_view)),
        hide_index=True,
        column_config={
            "股票": st.column_config.TextColumn(width="small"),
            "公司": st.column_config.TextColumn(width="medium"),
            "板块": st.column_config.TextColumn(width="medium"),
            "AI 标签": st.column_config.TextColumn(width="large"),
        },
    )
    if not positions.empty:
        ai_positions = positions[positions["ai_tags"].fillna("") != ""]
        if ai_positions.empty:
            st.info("当前三位虚拟人还没有 AI 标签持仓。")
        else:
            st.subheader("AI 持仓")
            ai_position_view = build_position_view(ai_positions, personas, symbols)
            render_position_cards(ai_position_view)

with tabs[5]:
    if reports.empty:
        st.info("暂无日报。")
    else:
        dates_desc = sorted(reports["date"].unique(), reverse=True)
        latest_report_date = dates_desc[0]
        recent_dates = sorted(dates_desc[:5])
        older_date_windows = historical_windows(dates_desc)
        st.subheader("最近 5 个交易日整合信息")
        st.caption(
            f"当前策略已更新到 {latest_report_date}。默认重点展示最近 5 个已生成交易日，"
            "更早的历史交易策略已折叠，展开后可按 5 日窗口查看。"
        )
        for _, persona in personas.iterrows():
            render_strategy_matrix(persona, recent_dates, reports, orders, trades)
        if older_date_windows:
            with st.expander("历史交易策略", expanded=False):
                for history_dates in older_date_windows:
                    start_date = history_dates[0]
                    end_date = history_dates[-1]
                    with st.expander(f"{start_date} 至 {end_date}", expanded=False):
                        for _, persona in personas.iterrows():
                            render_strategy_matrix(persona, history_dates, reports, orders, trades)
