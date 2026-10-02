import time
from nepse_data_api import Nepse

nepse = Nepse()

# All Thursdays, going back in steps of about 3 months
dates = ["2026-06-18", "2026-03-19", "2025-12-18", "2025-09-18",
         "2025-06-19", "2025-03-20", "2024-12-19", "2024-09-19"]

for d in dates:
    try:
        rows = nepse.get_today_price(date=d)
        print(d, "->", len(rows) if rows else 0, "rows")
    except Exception as ex:
        print(d, "-> error:", ex)
    time.sleep(3)