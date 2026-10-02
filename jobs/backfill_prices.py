import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from nepse_data_api import Nepse
from app.db import get_connection
from app.market import is_trading_weekday
from jobs.ingest_prices import init_prices

NEPAL = ZoneInfo("Asia/Kathmandu")
PAUSE = 3                  # seconds between requests (be gentle with NEPSE)
STOP_AFTER_EMPTY = 30      # stop after this many empty trading weekdays in a row
MIN_DATE = "2024-01-01"    # never go further back than this

def fetch_day(state, date_str):
    for attempt in range(3):
        rows = state["nepse"].get_today_price(date=date_str)
        if rows:
            return rows
        # Empty can mean a holiday OR an expired session, so refresh and retry
        time.sleep(10)
        state["nepse"] = Nepse()
    return []

def run():
    init_prices()
    conn = get_connection()
    have = {r[0] for r in conn.execute("SELECT DISTINCT trade_date FROM prices")}

    state = {"nepse": Nepse()}
    day = datetime.now(NEPAL).date() - timedelta(days=1)   # start from yesterday
    empty_streak = 0
    saved_days = 0

    while empty_streak < STOP_AFTER_EMPTY and day.isoformat() >= MIN_DATE:
        d = day.isoformat()
        day -= timedelta(days=1)

        if not is_trading_weekday(datetime.fromisoformat(d).date()):
            continue
        if d in have:
            empty_streak = 0
            continue

        rows = fetch_day(state, d)
        if not rows:
            empty_streak += 1
            print(f"{d}: no data (streak {empty_streak})")
            time.sleep(PAUSE)
            continue

        empty_streak = 0
        now = datetime.now(NEPAL).isoformat()
        for r in rows:
            close, prev = r.get("closePrice"), r.get("previousDayClosePrice")
            pct = round((close - prev) / prev * 100, 2) if close and prev else None
            conn.execute(
                """INSERT OR REPLACE INTO prices
                   (trade_date, symbol, name, open, high, low, close, prev_close,
                    volume, turnover, pct_change, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (r.get("businessDate") or d, r.get("symbol"), r.get("securityName"),
                 r.get("openPrice"), r.get("highPrice"), r.get("lowPrice"), close,
                 prev, r.get("totalTradedQuantity"), r.get("totalTradedValue"),
                 pct, now),
            )
        conn.commit()
        saved_days += 1
        print(f"{d}: saved {len(rows)} stocks")
        time.sleep(PAUSE)

    conn.close()
    print(f"\nDone. {saved_days} new days saved.")


if __name__ == "__main__":
    run()