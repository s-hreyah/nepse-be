import numpy as np
import pandas as pd

from jobs.forecast_vol import load

HORIZONS = [1, 5, 10, 20]

px = load()
parts = []
for sym, g in px.groupby("symbol"):
    g = g.sort_values("trade_date").reset_index(drop=True)
    p = g["adj_close"]
    r = p.pct_change() * 100
    m20 = r.abs().rolling(20).mean()
    for h in HORIZONS:
        parts.append(pd.DataFrame({
            "symbol": sym, "date": g["trade_date"], "h": h,
            "fwd": (p.shift(-h) / p - 1) * 100,      # return over the next h days
            "m20": m20,
        }))
df = pd.concat(parts, ignore_index=True).dropna()
df = df[df["m20"] > 0]

dates = sorted(df["date"].unique())
cut = dates[len(dates) // 2]
print(f"Band multiplier fitted before {cut}, checked after it\n")
print(f"{'days':>4} {'multiplier':>11} {'first half':>11} {'second half':>12} "
      f"{'windows':>8} {'up share':>9} {'down share':>11}")

for h in HORIZONS:
    d = df[df["h"] == h]
    a, b = d[d["date"] < cut], d[d["date"] >= cut]
    k = (a["fwd"].abs() / (a["m20"] * np.sqrt(h))).quantile(0.8)
    hit1 = (a["fwd"].abs() <= k * a["m20"] * np.sqrt(h)).mean()
    hit2 = (b["fwd"].abs() <= k * b["m20"] * np.sqrt(h)).mean()
    print(f"{h:>4} {k:>11.2f} {hit1:>11.1%} {hit2:>12.1%} {len(b):>8} "
          f"{(b['fwd'] > 0).mean():>9.1%} {(b['fwd'] < 0).mean():>11.1%}")

# does the past 20-day return say anything about the next 10 days? (day-level, so stocks count once per day)
parts = []
for sym, g in px.groupby("symbol"):
    g = g.sort_values("trade_date").reset_index(drop=True)
    p = g["adj_close"]
    parts.append(pd.DataFrame({"date": g["trade_date"],
                               "past20": (p / p.shift(20) - 1) * 100,
                               "next10": (p.shift(-10) / p - 1) * 100}))
m = pd.concat(parts).dropna().groupby("date").mean()
print(f"\nMomentum check, market-wide by day: correlation of past 20-day return "
      f"with next 10-day return = {m['past20'].corr(m['next10']):.3f} over {len(m)} days")
print("(windows overlap, so the real evidence is far smaller than that day count)")