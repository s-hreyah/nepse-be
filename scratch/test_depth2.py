import time
from nepse_data_api import Nepse

n = Nepse()

dates = ["2026-09-15", "2026-03-15", "2025-09-16", "2025-06-16",
         "2024-09-17", "2024-03-12", "2023-03-14", "2021-09-15"]
tests = {
    "today_price": lambda d: n.get_today_price(date=d),
    "daily_trade": lambda d: n.get_daily_trade(d),
    "stocks":      lambda d: n.get_stocks(date=d),
    "marcap":      lambda d: n.get_marcapbydate(date=d),
}

print("Rows returned per date and endpoint:")
for d in dates:
    out = []
    for name, fn in tests.items():
        try:
            r = fn(d)
            out.append(f"{name}={len(r) if hasattr(r, '__len__') else r}")
        except Exception as e:
            out.append(f"{name}=err")
        time.sleep(1)
    print(d, "  ".join(out))


def flat(d, p=""):
    o = {}
    for k, v in d.items():
        if isinstance(v, dict):
            o.update(flat(v, f"{p}{k}."))
        else:
            o[f"{p}{k}"] = v
    return o


print("\nSBL dividend entries, structured fields:")
keys = ["companyNews.addedDate",
        "companyNews.dividendsNotice.financialYear.fyName",
        "companyNews.dividendsNotice.cashDividend",
        "companyNews.dividendsNotice.bonusShare",
        "companyNews.dividendsNotice.rightShare"]
for it in n.get_dividends("SBL"):
    f = flat(it)
    print([f.get(k) for k in keys])