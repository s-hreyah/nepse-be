import time
from datetime import datetime
from zoneinfo import ZoneInfo

from nepse_data_api import Nepse
from app.db import get_connection
from jobs.ingest_prices import init_prices
from jobs.backfill_prices import fetch_day

NEPAL = ZoneInfo("Asia/Kathmandu")
PAUSE = 3


def save_day(conn, d, rows):
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


def run():
    init_prices()
    state = {"nepse": Nepse()}
    today = datetime.now(NEPAL).date().isoformat()

    idx = state["nepse"].get_index_history(
        index="NEPSE", start_date="2025-09-01", end_date=today)
    calendar = sorted({r["businessDate"] for r in idx})

    fridays = [d for d in calendar
               if datetime.fromisoformat(d).weekday() == 4]
    print("First Friday trading day in the calendar:",
          fridays[0] if fridays else None)

    conn = get_connection()
    have = {r[0] for r in conn.execute("SELECT DISTINCT trade_date FROM prices")}
    missing = [d for d in calendar if d not in have]
    print(f"{len(missing)} missing trading days to fetch\n")

    saved = 0
    failed = []
    for d in reversed(missing):          # newest first
        rows = fetch_day(state, d)
        if rows:
            save_day(conn, d, rows)
            saved += 1
            print(f"{d}: saved {len(rows)} stocks")
        else:
            failed.append(d)
            print(f"{d}: no data")
        time.sleep(PAUSE)

    conn.close()
    print(f"\nDone. {saved} days saved, {len(failed)} failed.")
    if failed:
        print("Failed:", failed)


if __name__ == "__main__":
    run()