# 虚拟美股投资世界

一个本机运行的虚拟美股投资观察系统。三个虚拟投资人各持有 20,000 美元，在大型美股池中进行纯虚拟交易，并特别观察 AI 产业链股票。

这个项目更接近一个“会每天更新的虚拟投资世界”，而不只是静态回测：

- 3 个不同风格的虚拟投资人格：稳健质量型、成长动量型、逆向价值型
- 使用真实 Yahoo Finance 日线数据更新最近一个已收盘的美股交易日
- 自动生成每日市场摘要、AI 产业链观察、虚拟订单、成交复盘和交易计划
- 通过 Streamlit dashboard 查看持仓、收益曲线、订单交易和最近 5 个交易日策略

适合用来观察不同投资风格在同一批美股与 AI 相关标的上的日常决策差异，而不是作为真实投资建议或自动交易系统。

## 快速开始

```bash
python3 run_daily.py --reset --demo-days 8
python3 -m streamlit run app.py
```

如果尚未安装 Streamlit：

```bash
python3 -m pip install -r requirements.txt
```

默认只使用真实日线行情。若真实行情拉取失败，系统会报错，而不会悄悄用演示价格。核心交易引擎和测试只依赖 Python 标准库，真实行情默认来自 Yahoo Finance chart 接口。

## 常用命令

```bash
python3 run_daily.py
python3 run_daily.py --date 2026-05-30
python3 run_daily.py --reset --demo-days 30
python3 backfill.py --days 30
python3 -m unittest discover -s tests
```

只有在明确想离线体验功能时，才使用演示合成行情：

```bash
python3 run_daily.py --reset --demo-days 30 --allow-synthetic
```

## 目录

- `app.py`: Streamlit dashboard
- `run_daily.py`: 每日流程入口
- `backfill.py`: 补齐多日真实行情数据
- `virtual_trader/`: 数据库、行情、策略、成交引擎和日报逻辑
- `tests/`: 交易规则测试

## 数据与边界

- 默认数据库：`data/virtual_trader.sqlite3`
- 默认每个虚拟投资人初始资金：`20,000 USD`
- 只做多股票，不做空、不融资、不使用期权或杠杆
- 日内成交使用 OHLC 区间代理，不接分钟级行情
- 项目仅用于虚拟模拟、观察和研究，不构成真实投资建议
