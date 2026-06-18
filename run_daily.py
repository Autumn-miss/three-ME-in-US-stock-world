from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from virtual_trader.config import DB_PATH
from virtual_trader.daily import run_daily
from virtual_trader.db import connect, init_db, one, reset_simulation, seed_defaults
from virtual_trader.market_data import next_business_day, previous_business_day


def latest_closed_us_trading_day(now: datetime | None = None) -> date:
    eastern = ZoneInfo("America/New_York")
    current = now.astimezone(eastern) if now else datetime.now(eastern)
    current_date = current.date()
    if current.weekday() < 5 and current.hour >= 17:
        return current_date
    return previous_business_day(current_date)


def parse_date(value: str | None) -> date:
    if not value:
        return latest_closed_us_trading_day()
    return datetime.strptime(value, "%Y-%m-%d").date()


def normalize_business_day(day: date) -> date:
    if day.weekday() < 5:
        return day
    return previous_business_day(day)


def completed_report_days(conn) -> list[date]:
    persona_count_row = one(conn, "SELECT COUNT(*) AS count FROM personas")
    persona_count = int(persona_count_row["count"]) if persona_count_row else 0
    if persona_count == 0:
        return []
    rows = conn.execute(
        """
        SELECT date
        FROM daily_reports
        GROUP BY date
        HAVING COUNT(DISTINCT persona_id) = ?
        ORDER BY date
        """,
        (persona_count,),
    ).fetchall()
    return [datetime.strptime(row["date"], "%Y-%m-%d").date() for row in rows]


def trading_days_to_run(conn, end_date: date) -> list[date]:
    completed_days = completed_report_days(conn)
    if not completed_days:
        return [end_date]

    completed_set = set(completed_days)
    earliest_report_day = completed_days[0]
    latest_report_day = completed_days[-1]
    first_missing_day: date | None = None
    current = earliest_report_day
    while current <= end_date:
        if current.weekday() < 5 and current not in completed_set:
            first_missing_day = current
            break
        current = next_business_day(current)

    if first_missing_day:
        start_day = first_missing_day
    elif latest_report_day < end_date:
        start_day = next_business_day(latest_report_day)
    else:
        return [end_date]

    days: list[date] = []
    current = start_day
    while current <= end_date:
        days.append(current)
        current = next_business_day(current)
    return days or [end_date]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the virtual US stock investor daily workflow.")
    parser.add_argument("--date", help="Run date in YYYY-MM-DD format. Defaults to the latest closed US trading weekday.")
    parser.add_argument(
        "--demo-days",
        type=int,
        default=0,
        help="Run multiple consecutive weekdays ending at --date/latest closed US trading weekday.",
    )
    parser.add_argument("--allow-synthetic", action="store_true", help="Allow synthetic demo prices if real data fails.")
    parser.add_argument("--reset", action="store_true", help="Reset portfolios, orders, trades, reports, snapshots, and cached prices.")
    args = parser.parse_args()

    requested_date = parse_date(args.date)
    end_date = normalize_business_day(requested_date)
    if end_date != requested_date:
        print(f"{requested_date.isoformat()} is not a trading weekday; using {end_date.isoformat()} instead.")
    with connect(DB_PATH) as conn:
        init_db(conn)
        seed_defaults(conn)
        if args.reset:
            reset_simulation(conn)
            seed_defaults(conn)
        if args.demo_days > 0:
            start = end_date - timedelta(days=args.demo_days - 1)
            current = start
            while current <= end_date:
                if current.weekday() < 5:
                    run_daily(conn, current, allow_synthetic=args.allow_synthetic)
                current += timedelta(days=1)
        else:
            for trading_day in trading_days_to_run(conn, end_date):
                run_daily(conn, trading_day, allow_synthetic=args.allow_synthetic)

    print(f"Daily workflow complete. Database: {DB_PATH}")


if __name__ == "__main__":
    main()
