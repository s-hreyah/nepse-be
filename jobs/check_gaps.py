from nepse_data_api import Nepse
from app.db import get_connection

nepse = Nepse()
idx = nepse.get_index_history(index="NEPSE", start_date="2025-09-01", end_date="2026-10-01")
calendar = sorted({r["businessDate"] for r in idx})
print(f"Trading days per the index: {len(calendar)} ({calendar[0]} to {calendar[-1]})")

conn = get_connection()
have = {r[0] for r in conn.execute("SELECT DISTINCT trade_date FROM prices")}
conn.close()

missing = [d for d in calendar if d not in have]
print(f"Days in prices table:       {len(have)}")
print(f"Missing trading days:       {len(missing)}")
print("Missing:", missing)