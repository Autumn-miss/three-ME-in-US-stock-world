from __future__ import annotations

import argparse
from datetime import date, timedelta

from virtual_trader.config import DB_PATH
from virtual_trader.daily import ensure_market_data_for_date
from virtual_trader.db import connect, init_db, seed_defaults


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill market data for the virtual trader project.")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--allow-synthetic", action="store_true", help="Allow synthetic demo prices if real data fails.")
    args = parser.parse_args()

    today = date.today()
    with connect(DB_PATH) as conn:
        init_db(conn)
        seed_defaults(conn)
        for offset in range(args.days - 1, -1, -1):
            day = today - timedelta(days=offset)
            if day.weekday() < 5:
                ensure_market_data_for_date(conn, day, allow_synthetic=args.allow_synthetic)
    print(f"Backfilled {args.days} calendar days into {DB_PATH}")


if __name__ == "__main__":
    main()
