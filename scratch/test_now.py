from datetime import datetime
from zoneinfo import ZoneInfo
from nepse_data_api import Nepse

nepse = Nepse()
print("Now:", datetime.now(ZoneInfo("Asia/Kathmandu")))
print("Market status:", nepse.get_market_status())

s = nepse.get_stocks()
print("get_stocks rows:", len(s) if s else s)

t = nepse.get_today_price()
print("get_today_price rows:", len(t) if t else t)
if t:
    print("businessDate of first row:", t[0].get("businessDate"))