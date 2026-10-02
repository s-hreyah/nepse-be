import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from nepse_data_api import Nepse
from app.db import get_connection
from app.market import is_trading_weekday

NEPAL = ZoneInfo("Asia/Kathmandu")
MIN_ROWS = 250   # a full day has about 330 rows; fewer means before the close or a holiday


def init_prices():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            trade_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT,
            open REAL, high REAL, low REAL, close REAL,
            prev_close REAL,
            volume INTEGER,
            turnover REAL,
            pct_change REAL,
            fetched_at TEXT,
            PRIMARY KEY (trade_date, symbol)
        )
    """)
    conn.commit()
    conn.close()


def fetch(date_str):
    for _ in range(3):
        rows = Nepse().get_today_price(date=date_str)   # fresh session each try
        if rows:
            return rows
        time.sleep(10)
    return []


def run(date_str=None):
    init_prices()
    now = datetime.now(NEPAL)
    date_str = date_str or now.date().isoformat()

    if not is_trading_weekday(datetime.fromisoformat(date_str).date()):
        print(f"{date_str}: weekend, nothing saved")
        return

    rows = fetch(date_str)
    if len(rows) < MIN_ROWS:
        print(f"{date_str}: only {len(rows)} rows (before the close or a holiday), nothing saved")
        return

    conn = get_connection()
    for r in rows:
        close, prev = r.get("closePrice"), r.get("previousDayClosePrice")
        pct = round((close - prev) / prev * 100, 2) if close and prev else None
        conn.execute(
            """INSERT OR REPLACE INTO prices
               (trade_date, symbol, name, open, high, low, close, prev_close,
                volume, turnover, pct_change, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (r.get("businessDate") or date_str, r.get("symbol"), r.get("securityName"),
             r.get("openPrice"), r.get("highPrice"), r.get("lowPrice"), close, prev,
             r.get("totalTradedQuantity"), r.get("totalTradedValue"), pct, now.isoformat()),
        )
    conn.commit()
    conn.close()
    print(f"{date_str}: saved {len(rows)} stocks")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)