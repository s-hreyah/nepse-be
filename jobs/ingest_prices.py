from datetime import datetime
from zoneinfo import ZoneInfo

from nepse_data_api import Nepse
from app.db import get_connection
from app.market import is_trading_weekday

NEPAL = ZoneInfo("Asia/Kathmandu")


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


def run():
    init_prices()
    now = datetime.now(NEPAL)

    if not is_trading_weekday(now.date()):
        print("Weekend: market closed, nothing saved")
        return

    stocks = Nepse().get_stocks()
    if not stocks:
        print("No stocks returned, nothing saved")
        return

    trade_date = now.strftime("%Y-%m-%d")
    conn = get_connection()
    for s in stocks:
        conn.execute(
            """INSERT OR REPLACE INTO prices
               (trade_date, symbol, name, open, high, low, close, prev_close,
                volume, turnover, pct_change, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (trade_date, s.get("symbol"), s.get("securityName"),
             s.get("openPrice"), s.get("highPrice"), s.get("lowPrice"),
             s.get("lastTradedPrice"), s.get("previousClose"),
             s.get("totalTradeQuantity"), s.get("totalTradeValue"),
             s.get("percentageChange"), now.isoformat()),
        )
    conn.commit()
    conn.close()
    print(f"{trade_date}: saved {len(stocks)} stocks")


if __name__ == "__main__":
    run()