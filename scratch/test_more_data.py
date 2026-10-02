import json
from nepse_data_api import Nepse

n = Nepse()


def show(label, fn, *a, **kw):
    print(f"\n=== {label} ===")
    try:
        d = fn(*a, **kw)
    except Exception as e:
        print("error:", e)
        return None
    print(type(d).__name__, len(d) if hasattr(d, "__len__") else "")
    items = d if isinstance(d, list) else [d]
    for x in items[:2]:
        print(json.dumps(x, default=str)[:400])
    return d


# find SBL's security id
secs = n.get_security_list()
sbl = next((s for s in secs if s.get("symbol") == "SBL"), None)
print("SBL record:", json.dumps(sbl, default=str)[:300])
sid = sbl.get("id") if sbl else None

if sid:
    for label, start, end in [("chart, last year", "2025-10-01", "2026-10-01"),
                              ("chart, 2022", "2022-01-01", "2022-12-31"),
                              ("chart, 2018", "2018-01-01", "2018-12-31")]:
        d = show(label, n.get_historical_chart, sid, start_date=start, end_date=end)
        if isinstance(d, list) and d:
            print("date range:", d[0], "...", d[-1])

show("dividends SBL", n.get_dividends, "SBL")
show("company news SBL", n.get_company_news, "SBL")
show("agm SBL", n.get_agm, "SBL")