from __future__ import annotations

import csv
import hashlib
import json
import math
import ssl
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .config import INDEX_SYMBOLS


def previous_business_day(day: date) -> date:
    current = day - timedelta(days=1)
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def next_business_day(day: date) -> date:
    current = day + timedelta(days=1)
    while current.weekday() >= 5:
        current += timedelta(days=1)
    return current


def fetch_stooq_daily(symbol: str, day: date, timeout: float = 4.0) -> dict[str, float | int | str] | None:
    code = symbol.lower()
    if symbol.upper() not in INDEX_SYMBOLS:
        code = f"{code}.us"
    params = urllib.parse.urlencode(
        {
            "s": code,
            "d1": day.strftime("%Y%m%d"),
            "d2": day.strftime("%Y%m%d"),
            "i": "d",
        }
    )
    url = f"https://stooq.com/q/d/l/?{params}"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        text = response.read().decode("utf-8")
    parsed = list(csv.DictReader(text.splitlines()))
    if not parsed:
        return None
    row = parsed[-1]
    if row.get("Close") in (None, "", "0"):
        return None
    return {
        "symbol": symbol,
        "date": row["Date"],
        "open": float(row["Open"]),
        "high": float(row["High"]),
        "low": float(row["Low"]),
        "close": float(row["Close"]),
        "volume": int(float(row.get("Volume") or 0)),
        "source": "stooq",
    }


def ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def fetch_yahoo_daily(symbol: str, day: date, timeout: float = 20.0) -> dict[str, float | int | str] | None:
    eastern = ZoneInfo("America/New_York")
    start = datetime(day.year, day.month, day.day, tzinfo=eastern)
    end = start + timedelta(days=1)
    params = urllib.parse.urlencode(
        {
            "period1": int(start.timestamp()),
            "period2": int(end.timestamp()),
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout, context=ssl_context()) as response:
        payload = json.loads(response.read().decode("utf-8"))

    chart = payload.get("chart", {})
    if chart.get("error"):
        raise RuntimeError(chart["error"])
    results = chart.get("result") or []
    if not results:
        return None
    result = results[0]
    timestamps = result.get("timestamp") or []
    quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    if not timestamps:
        return None

    for index, timestamp in enumerate(timestamps):
        market_date = datetime.fromtimestamp(timestamp, tz=eastern).date()
        if market_date != day:
            continue
        open_price = quotes.get("open", [None])[index]
        high = quotes.get("high", [None])[index]
        low = quotes.get("low", [None])[index]
        close = quotes.get("close", [None])[index]
        volume = quotes.get("volume", [0])[index] or 0
        if None in (open_price, high, low, close):
            return None
        return {
            "symbol": symbol,
            "date": market_date.isoformat(),
            "open": round(float(open_price), 4),
            "high": round(float(high), 4),
            "low": round(float(low), 4),
            "close": round(float(close), 4),
            "volume": int(volume),
            "source": "yahoo",
        }
    return None


def synthetic_daily(symbol: str, day: date) -> dict[str, float | int | str]:
    digest = hashlib.sha256(symbol.encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    base = 40 + (seed % 420)
    day_index = (day - date(2020, 1, 1)).days
    trend = day_index * (0.015 + (seed % 17) / 5000)
    seasonal = math.sin(day_index / 9 + (seed % 31)) * (1.2 + (seed % 7) / 5)
    noise = math.sin(day_index * 1.7 + (seed % 11)) * 0.7
    close = max(5.0, base + trend + seasonal + noise)
    open_price = close * (1 + math.sin(day_index + seed) * 0.006)
    spread = close * (0.012 + ((seed + day_index) % 9) / 1500)
    high = max(open_price, close) + spread
    low = max(1.0, min(open_price, close) - spread)
    volume = 1_000_000 + (seed % 20_000_000)
    return {
        "symbol": symbol,
        "date": day.isoformat(),
        "open": round(open_price, 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "close": round(close, 2),
        "volume": volume,
        "source": "synthetic",
    }


def get_daily_price(symbol: str, day: date, allow_synthetic: bool = False) -> dict[str, float | int | str]:
    errors: list[str] = []
    for attempt in range(3):
        try:
            fetched = fetch_yahoo_daily(symbol, day)
            if fetched:
                return fetched
            errors.append("yahoo: no daily bar returned")
        except Exception as exc:
            errors.append(f"yahoo attempt {attempt + 1}: {exc}")
        if attempt < 2:
            time.sleep(0.8 * (attempt + 1))

    if allow_synthetic:
        price = synthetic_daily(symbol, day)
        price["source"] = "synthetic_demo"
        return price

    detail = "; ".join(errors) if errors else "no daily bar returned"
    raise RuntimeError(f"Unable to fetch real daily price for {symbol} on {day.isoformat()} ({detail})")


def get_demo_daily_price(symbol: str, day: date) -> dict[str, float | int | str]:
    return synthetic_daily(symbol, day)


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()
