from nepse_data_api import Nepse

n = Nepse()


def flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(flat(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out


for label, fn in [("dividends", n.get_dividends), ("agm", n.get_agm), ("news", n.get_company_news)]:
    items = fn("SBL")
    print(f"\n=== {label}: {len(items)} items ===")
    if items:
        print("keys:", sorted(flat(items[0]).keys()))
    for it in items:
        f = flat(it)
        dates = {k: v for k, v in f.items() if "date" in k.lower() or "time" in k.lower()}
        body = (f.get("companyNews.newsBody") or "").replace("\n", " | ")[:140]
        print(dates, body)