import numpy as np
import pandas as pd

from app.db import get_connection

TOP_N, MIN_SHARE, START = 30, 0.95, 120

conn = get_connection()
df = pd.read_sql_query(
    "SELECT p.trade_date, p.symbol, p.adj_close, p.volume, p.turnover "
    "FROM prices p JOIN companies c ON c.symbol = p.symbol "
    "WHERE c.instrument_type = 'Equity' ORDER BY p.symbol, p.trade_date", conn)
conn.close()

n_days = df["trade_date"].nunique()
t = df[df["volume"] > 0].groupby("symbol").agg(days=("trade_date", "nunique"),
                                              med=("turnover", "median"))
liquid = t[t["days"] / n_days >= MIN_SHARE].sort_values("med", ascending=False).head(TOP_N)

parts = []
for sym in liquid.index:
    s = df[(df["symbol"] == sym) & (df["volume"] > 0)].reset_index(drop=True)
    r = s["adj_close"].pct_change() * 100                      # daily return, %
    f = pd.DataFrame({
        "symbol": sym, "trade_date": s["trade_date"], "actual": r,
        "naive": 0.0,                                          # tomorrow = today
        "drift": r.expanding().mean().shift(1),                # average past return
        "yesterday": r.shift(1),                               # repeat yesterday's move
    })
    parts.append(f.iloc[START:].dropna())
test = pd.concat(parts, ignore_index=True)
print(f"{len(liquid)} stocks, {len(test)} out-of-sample predictions\n")

rows = []
for m in ("naive", "drift", "yesterday"):
    e = test["actual"] - test[m]
    rows.append((m, e.abs().mean(), np.sqrt((e ** 2).mean())))
res = pd.DataFrame(rows, columns=["model", "MAE_%", "RMSE_%"]).round(3)
res["MAE_vs_naive"] = (res["MAE_%"] / res.loc[0, "MAE_%"]).round(3)
print(res.to_string(index=False))

up = (test["actual"] > 0).mean() * 100
print(f"\nDirection (next day up?): test days up {up:.1f}%, down or flat {100 - up:.1f}%")
print(f"  always down:         {100 - up:.1f}% correct")
print(f"  always up:           {up:.1f}% correct")
same = ((test["yesterday"] > 0) == (test["actual"] > 0)).mean() * 100
print(f"  same as yesterday:   {same:.1f}% correct")

by_day = test.groupby("trade_date")["actual"].agg(["mean", "std"])
print(f"\nAverage daily market move: std {by_day['mean'].std():.2f}%, "
      f"average spread between stocks {by_day['std'].mean():.2f}%")