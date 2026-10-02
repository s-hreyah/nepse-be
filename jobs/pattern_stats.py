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
    sig["trade_date"] = s["trade_date"]
    parts.append(sig.dropna(subset=["next_ret"]))
all_ = pd.concat(parts, ignore_index=True)

base_n = len(all_)
base_up = (all_["next_ret"] > 0).mean()
base_avg = all_["next_ret"].mean()
print(f"All days: {base_n} observations, next day up {base_up:.1%}, average {base_avg:+.3f}%\n")
def split(x):
    r = x["next_ret"]
    return ((r > 0.005).mean() * 100, (r.abs() <= 0.005).mean() * 100, (r < -0.005).mean() * 100)


def line(name, hit):
    n = len(hit)
    if n == 0:
        return (name, 0, None, None, None, None, None)
    up_share = (hit["next_ret"] > 0).mean()
    z = (up_share - base_up) / np.sqrt(base_up * (1 - base_up) / n)
    u, f, d = split(hit)
    return (name, n, round(hit["next_ret"].mean(), 3), round(z, 2),
            round(u, 1), round(f, 1), round(d, 1))


rows = [line("all_days", all_)] + [line(name, all_[all_[name]]) for name in RULES]
out = pd.DataFrame(rows, columns=["pattern", "times", "avg_next", "z", "up", "flat", "down"])
print(out.to_string(index=False))
for name in ("bear_marubozu", "bull_marubozu"):
    hit = all_[all_[name]]
    by_day = hit.groupby("trade_date")["next_ret"].agg(["size", "mean"])
    print(f"\n{name}: {len(hit)} cases on {len(by_day)} distinct days. Busiest days:")
    print(by_day.sort_values("size", ascending=False).head(5).round(2))
    print("share of days with a positive average next-day return:",
          round((by_day["mean"] > 0).mean() * 100, 1), "%")

conn.execute("DROP TABLE IF EXISTS pattern_stats")
out.to_sql("pattern_stats", conn, index=False)

day_all = all_.groupby("trade_date")["next_ret"].mean()
print("\nAll days: share of days with positive average next-day return:",
      round((day_all > 0).mean() * 100, 1), "%")

skip = {"2026-03-09", "2026-04-05"}
for name in ("bear_marubozu", "bull_marubozu"):
    hit = all_[all_[name] & ~all_["trade_date"].isin(skip)]
    m = hit.groupby("trade_date")["next_ret"].mean()
    print(name, "without the two odd days:", len(hit), "cases,",
          "average next day", round(hit["next_ret"].mean(), 3), "%,",
          "positive days", round((m > 0).mean() * 100, 1), "%")
conn.close()