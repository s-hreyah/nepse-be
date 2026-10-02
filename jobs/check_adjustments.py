from app.db import get_connection

conn = get_connection()

sql = """
WITH x AS (
  SELECT p.trade_date, p.symbol, p.close, p.prev_close, p.pct_change, p.volume,
         LAG(p.close) OVER (PARTITION BY p.symbol ORDER BY p.trade_date) AS lag_close
  FROM prices p JOIN companies c ON c.symbol = p.symbol
  WHERE c.instrument_type = 'Equity'
)
SELECT trade_date, symbol, lag_close, prev_close,
       ROUND((prev_close - lag_close) / lag_close * 100, 2) AS gap_pct
FROM x
WHERE lag_close IS NOT NULL AND ABS(prev_close - lag_close) > 0.01 * lag_close
ORDER BY trade_date DESC
"""
adj = conn.execute(sql).fetchall()
print(f"Days where prev_close differs from the last stored close by more than 1%: {len(adj)}")
for r in adj[:15]:
    print(r)

limit = conn.execute(
    """SELECT MAX(ABS(p.pct_change)), SUM(ABS(p.pct_change) > 15.5)
       FROM prices p JOIN companies c ON c.symbol = p.symbol
       WHERE c.instrument_type = 'Equity' AND p.volume > 0"""
).fetchone()
print(f"\nLargest daily move: {limit[0]}%   Days beyond 15.5%: {limit[1]}")
conn.close()