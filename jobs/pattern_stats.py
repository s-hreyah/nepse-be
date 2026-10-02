import numpy as np
import pandas as pd

from app.db import get_connection
from app.patterns import detect, RULES

TOP_N, MIN_SHARE = 30, 0.95

conn = get_connection()
df = pd.read_sql_query(
    "SELECT p.trade_date, p.symbol, p.open, p.high, p.low, p.close, p.adj_close, "
    "p.volume, p.turnover FROM prices p JOIN companies c ON c.symbol = p.symbol "
    "WHERE c.instrument_type = 'Equity' ORDER BY p.symbol, p.trade_date", conn)

# liquid stocks: traded on at least 95% of days, top 30 by median turnover
n_days = df["trade_date"].nunique()
t = df[df["volume"] > 0].groupby("symbol").agg(days=("trade_date", "nunique"),
                                              med=("turnover", "median"))
liquid = t[t["days"] / n_days >= MIN_SHARE].sort_values("med", ascending=False).head(TOP_N)
print(f"{len(liquid)} liquid stocks, {n_days} trading days")

parts = []
for sym in liquid.index:
    s = df[df["symbol"] == sym].reset_index(drop=True)
    f = s["adj_close"] / s["close"].where(s["close"] > 0)
    for col in ("open", "high", "low"):
        s[f"adj_{col}"] = s[col] * f
    s = s[s["volume"] > 0].reset_index(drop=True)      # drop days with no trades
    sig = detect(s)
    sig["symbol"] = sym
    sig["next_ret"] = (s["adj_close"].shift(-1) / s["adj_close"] - 1) * 100
    parts.append(sig.dropna(subset=["next_ret"]))
all_ = pd.concat(parts, ignore_index=True)

base_n = len(all_)
base_up = (all_["next_ret"] > 0).mean()
base_avg = all_["next_ret"].mean()
print(f"All days: {base_n} observations, next day up {base_up:.1%}, average {base_avg:+.3f}%\n")

rows = []
for name in RULES:
    hit = all_[all_[name]]
    n = len(hit)
    if n == 0:
        rows.append((name, 0, None, None, None))
        continue
    up = (hit["next_ret"] > 0).mean()
    z = (up - base_up) / np.sqrt(base_up * (1 - base_up) / n)
    rows.append((name, n, up, hit["next_ret"].mean(), z))

out = pd.DataFrame(rows, columns=["pattern", "times", "next_up", "avg_next_%", "z"])
out["next_up"] = (out["next_up"] * 100).round(1)
print(out.round(3).to_string(index=False))

conn.execute("DROP TABLE IF EXISTS pattern_stats")
out.assign(base_up=round(base_up * 100, 1), base_avg=round(base_avg, 3)) \
   .to_sql("pattern_stats", conn, index=False)

def split(x):
    r = x["next_ret"]
    return (round((r > 0.005).mean() * 100, 1),
            round((r.abs() <= 0.005).mean() * 100, 1),
            round((r < -0.005).mean() * 100, 1))

print("\nNext day: (up %, flat %, down %)")
print(f"{'all days':>15} n={len(all_):>5}", split(all_))
for name in RULES:
    hit = all_[all_[name]]
    if len(hit):
        print(f"{name:>15} n={len(hit):>5}", split(hit))
conn.close()