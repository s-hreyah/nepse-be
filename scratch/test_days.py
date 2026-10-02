import time
from nepse_data_api import Nepse

nepse = Nepse()

# Sept 25 = Friday, Sept 26 = Saturday, Sept 27 = Sunday, Sept 28 = Monday
for d in ["2026-09-25", "2026-09-26", "2026-09-27", "2026-09-28"]:
    rows = nepse.get_today_price(date=d)
    print(d, "->", len(rows) if rows else 0, "rows")
    time.sleep(5)