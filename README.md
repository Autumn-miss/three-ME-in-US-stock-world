# 虚拟美股投资世界

一个本机运行的虚拟美股投资观察系统。三个虚拟投资人各持有 20,000 美元，在大型美股池中进行纯虚拟交易，并特别观察 AI 产业链股票。

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
