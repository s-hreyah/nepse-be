import time
from nepse_data_api import Nepse

from app.db import get_connection

n = Nepse()
START, END = "2025-10-01", "2026-10-01"   # END is yesterday, so no live row

def get(idx):
    return sorted(
        n.get_index_history(index=idx, start_date=START, end_date=END, size=500),
        key=lambda r: r["businessDate"],
    )

rows = get(58)
print("NEPSE index rows:", len(rows))
for r in rows[:2] + rows[-2:]:
    print(r["businessDate"], r["closingIndex"], r["openIndex"], r["turnoverValue"])

zero = [r["businessDate"] for r in rows if not r["closingIndex"]]
print("rows with closingIndex 0:", zero)

conn = get_connection()
price_days = {d for (d,) in conn.execute("SELECT DISTINCT trade_date FROM prices")}
conn.close()
index_days = {r["businessDate"] for r in rows}
print("in prices but not in index:", sorted(price_days - index_days)[:10])
print("in index but not in prices:", sorted(index_days - price_days)[:10])

print("\nSector indices:")
for s in n.get_sub_indices():
    time.sleep(1)
    h = get(s["id"])
    print(s["id"], s["index"], len(h), h[-1]["businessDate"] if h else None)