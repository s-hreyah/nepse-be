import sys
from app.db import get_connection

symbol = sys.argv[1] if len(sys.argv) > 1 else "SPHL"
conn = get_connection()

print(f"=== Last 8 days of {symbol} ===")
print("date        close   prev_close  pct    volume   yesterday_close_in_our_table")
rows = conn.execute(
    "SELECT trade_date, close, prev_close, pct_change, volume FROM prices "
    "WHERE symbol = ? ORDER BY trade_date DESC LIMIT 8", (symbol,)).fetchall()
dates = [r[0] for r in rows]
closes = {r[0]: r[1] for r in rows}
for i, (d, close, prev, pct, vol) in enumerate(rows):
    yday = closes.get(dates[i + 1]) if i + 1 < len(dates) else None
    print(f"{d}  {close:<7} {prev:<11} {pct:<6} {vol:<8} {yday}")

print("\n=== Equity days with a move beyond 10% (volume > 0) ===")
big = conn.execute(
    """SELECT p.trade_date, p.symbol, p.prev_close, p.close, p.pct_change
       FROM prices p JOIN companies c ON c.symbol = p.symbol
       WHERE c.instrument_type = 'Equity' AND p.volume > 0
         AND ABS(p.pct_change) > 10
       ORDER BY p.trade_date DESC""").fetchall()
print("Count:", len(big))
for r in big[:15]:
    print(r)
conn.close()