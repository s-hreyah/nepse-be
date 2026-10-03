import os
import sqlite3

import numpy as np
import pandas as pd

from app.config import DB_PATH

EXT = os.path.join(os.path.dirname(DB_PATH), "external.db")
ext = sqlite3.connect(EXT)
r = pd.read_sql_query(
    "SELECT trade_date, symbol, ret, turnover, after_break, flag_bonus FROM returns_final", ext)
ext.close()

N_STOCKS, MIN_DAYS, HORIZONS = 30, 900, [5, 10, 20]

n = r.groupby("symbol").size()
med = r.groupby("symbol")["turnover"].median()
liquid = med[n[n >= MIN_DAYS].index].sort_values(ascending=False).head(N_STOCKS).index
print(f"{len(liquid)} stocks with {MIN_DAYS}+ trading days, top by median turnover")
print(" ".join(liquid))

dates = sorted(r["trade_date"].unique())
pos = {d: i for i, d in enumerate(dates)}

parts = {h: [] for h in HORIZONS}
for sym in liquid:
    g = r[r["symbol"] == sym].sort_values("trade_date").reset_index(drop=True)
    bad = (g["after_break"].astype(int) + g["flag_bonus"].astype(int)).clip(upper=1)
    c = np.log1p(g["ret"] / 100).cumsum()
    b = bad.cumsum()
    past = c - c.shift(20)
    pbad = b - b.shift(20)
    for h in HORIZONS:
        fwd = c.shift(-h) - c
        fbad = b.shift(-h) - b
        ok = (fbad == 0) & (pbad == 0) & fwd.notna() & past.notna()
        parts[h].append(pd.DataFrame({
            "date": g["trade_date"], "pos": g["trade_date"].map(pos),
            "fwd": np.expm1(fwd) * 100, "past": past})[ok])

for h in HORIZONS:
    d = pd.concat(parts[h])
    d = d[d["pos"] % h == 0]                      # windows that do not overlap
    up = d["fwd"] > 0
    mom = d["past"] > 0
    t = pd.DataFrame({"date": d["date"],
                      "always_up": up.astype(float),
                      "always_down": (~up).astype(float),
                      "momentum": (mom == up).astype(float),
                      "reversal": (mom != up).astype(float)})
    pdate = t.groupby("date").mean()              # one number per date
    pdate["year"] = pdate.index.str[:4]
    print(f"\n=== {h}-day windows: {len(pdate)} dates, {len(d)} stock-windows ===")
    by = pdate.groupby("year").agg(dates=("always_up", "size"), always_up=("always_up", "mean"),
                                   always_down=("always_down", "mean"),
                                   momentum=("momentum", "mean"), reversal=("reversal", "mean"))
    by.loc["all"] = [len(pdate)] + [pdate[c].mean() for c in
                                    ("always_up", "always_down", "momentum", "reversal")]
    show = by.copy()
    show["dates"] = show["dates"].astype(int)
    for c in ("always_up", "always_down", "momentum", "reversal"):
        show[c] = (show[c] * 100).round(1)
    print(show.to_string())
    for rule in ("momentum", "reversal"):
        for base in ("always_up", "always_down"):
            x = pdate[rule] - pdate[base]
            se = x.std() / np.sqrt(len(x))
            print(f"  {rule} minus {base}: {x.mean() * 100:+.1f} points, "
                  f"standard error {se * 100:.1f}")