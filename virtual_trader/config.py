from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "virtual_trader.sqlite3"

INITIAL_CASH = 20_000.0
SLIPPAGE_RATE = 0.0005
MAX_POSITION_WEIGHT = 0.35
MAX_OPEN_POSITIONS = 8
MIN_CASH_WEIGHT = 0.02

INDEX_SYMBOLS = ["SPY", "QQQ", "DIA"]

SYMBOLS = [
    ("AAPL", "Apple", "Consumer Technology", "devices,on-device AI"),
    ("MSFT", "Microsoft", "Cloud Software", "cloud,enterprise AI"),
    ("NVDA", "NVIDIA", "Semiconductors", "chips,accelerators,AI infrastructure"),
    ("GOOGL", "Alphabet", "Cloud Software", "cloud,AI models,ads"),
    ("AMZN", "Amazon", "Cloud Retail", "cloud,AI infrastructure"),
    ("META", "Meta Platforms", "Social Platforms", "AI models,ads,infrastructure"),
    ("AVGO", "Broadcom", "Semiconductors", "chips,networking,AI infrastructure"),
    ("TSLA", "Tesla", "Autos", "robotics,autonomy"),
    ("AMD", "Advanced Micro Devices", "Semiconductors", "chips,accelerators"),
    ("CRM", "Salesforce", "Enterprise Software", "enterprise AI"),
    ("ORCL", "Oracle", "Cloud Software", "cloud,data infrastructure"),
    ("ADBE", "Adobe", "Creative Software", "generative AI,software"),
    ("NOW", "ServiceNow", "Enterprise Software", "workflow AI,enterprise AI"),
    ("SNOW", "Snowflake", "Data Software", "data infrastructure,enterprise AI"),
    ("PLTR", "Palantir", "Data Software", "analytics,enterprise AI"),
    ("MU", "Micron", "Semiconductors", "memory,AI infrastructure"),
    ("SMCI", "Super Micro Computer", "Hardware", "servers,AI infrastructure"),
    ("ASML", "ASML", "Semiconductor Equipment", "lithography,semiconductor equipment"),
    ("TSM", "Taiwan Semiconductor", "Semiconductors", "foundry,chips"),
    ("ARM", "Arm Holdings", "Semiconductors", "chip architecture"),
    ("INTC", "Intel", "Semiconductors", "chips,foundry"),
    ("QCOM", "Qualcomm", "Semiconductors", "edge AI,chips"),
    ("ANET", "Arista Networks", "Networking", "networking,data centers"),
    ("VRT", "Vertiv", "Data Center Infrastructure", "power,cooling,data centers"),
    ("CEG", "Constellation Energy", "Energy", "power,data centers"),
    ("ETN", "Eaton", "Electrical Infrastructure", "power,data centers"),
    ("JPM", "JPMorgan Chase", "Financials", ""),
    ("V", "Visa", "Payments", ""),
    ("MA", "Mastercard", "Payments", ""),
    ("UNH", "UnitedHealth", "Healthcare", ""),
    ("LLY", "Eli Lilly", "Healthcare", ""),
    ("COST", "Costco", "Retail", ""),
    ("WMT", "Walmart", "Retail", ""),
    ("XOM", "Exxon Mobil", "Energy", ""),
    ("PG", "Procter & Gamble", "Consumer Staples", ""),
    ("HD", "Home Depot", "Retail", ""),
    ("MCD", "McDonald's", "Consumer", ""),
]
