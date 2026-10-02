from nepse_data_api import Nepse

nepse = Nepse()

# 1. One past trading day (a Thursday, one week ago)
rows = nepse.get_today_price(date="2026-09-24")
print("Rows for 2026-09-24:", len(rows) if rows else rows)
if rows:
    print("Field names:", list(rows[0].keys()))
    print("First row:", rows[0])

# 2. A much older day, to see how far back it goes
rows = nepse.get_today_price(date="2024-09-12")
print("\nRows for 2024-09-12:", len(rows) if rows else rows)

# 3. NEPSE index history
idx = nepse.get_index_history(index="NEPSE", start_date="2023-01-01", end_date="2026-09-30")
print("\nIndex rows:", len(idx) if idx else idx)
if idx:
    print("First:", idx[0])
    print("Last:", idx[-1])