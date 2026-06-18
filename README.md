# Virtual US Stock World

A local-first virtual US stock investing simulator. Three simulated investors each start with USD 20,000, trade virtually inside a large-cap US stock universe, and keep a close watch on AI-related names.

This project is designed as a living virtual market world that updates every day, not just a static backtest:

- 3 distinct investing personas: Quality & Stability, Growth & Momentum, and Contrarian Value
- Uses real Yahoo Finance daily market data to update the most recent closed US trading day
- Automatically generates market summaries, AI sector notes, virtual orders, trade reviews, and next-day plans
- Provides a Streamlit dashboard for holdings, return curves, executed trades, and the most recent 5 trading days of strategy output

It is useful for observing how different investing styles react to the same US stock universe and AI-related opportunities over time. It is not investment advice and it is not an automated live trading system.

## Quick Start

```bash
python3 run_daily.py --reset --demo-days 8
python3 -m streamlit run app.py
```

If Streamlit is not installed yet:

```bash
python3 -m pip install -r requirements.txt
```

By default, the project uses only real daily market data. If real quotes cannot be fetched, the run fails explicitly instead of silently falling back to demo prices. The core trading engine and tests rely only on the Python standard library, while real market data is fetched from the Yahoo Finance chart endpoint.

## Common Commands

```bash
python3 run_daily.py
python3 run_daily.py --date 2026-05-30
python3 run_daily.py --reset --demo-days 30
python3 backfill.py --days 30
python3 -m unittest discover -s tests
```

Use synthetic demo prices only when you intentionally want an offline product demo:

```bash
python3 run_daily.py --reset --demo-days 30 --allow-synthetic
```

## Project Structure

- `app.py`: Streamlit dashboard
- `run_daily.py`: daily workflow entry point
- `backfill.py`: backfills multiple days of real market data
- `virtual_trader/`: database, market data, strategies, execution engine, and daily report logic
- `tests/`: trading-rule test suite

## Data Model and Limits

- Default database: `data/virtual_trader.sqlite3`
- Default starting capital per simulated investor: `USD 20,000`
- Long-only stock trading, with no shorting, leverage, margin, or options
- Daily execution is approximated from OHLC ranges rather than intraday tick or minute data
- The project is for simulation, observation, and research only, not for real investment decisions
