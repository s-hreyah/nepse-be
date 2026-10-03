import os
import sqlite3

import pandas as pd

from app.config import DB_PATH
from jobs.forecast_vol import load

EXT = os.path.join(os.path.dirname(DB_PATH), "external.db")
ext = sqlite3.connect(EXT)
long = pd.read_sql_query(
    "SELECT trade_date, symbol, close, prev_close, volume FROM prices_long", ext)
ext.close()
long["trade_date"] = pd.to_datetime(long["trade_date"])
long = long[(long["close"] > 0) & (long["prev_close"] > 0)].sort_values(["symbol", "trade_date"])

main = sqlite3.connect(DB_PATH)
eq = set(pd.read_sql_query(
    "SELECT symbol FROM companies WHERE instrument_type = 'Equity'", main)["symbol"])
lo = pd.to_datetime(pd.read_sql_query("SELECT MIN(trade_date) AS d FROM prices", main)["d"][0])
ca = pd.read_sql_query("SELECT symbol, book_close, bonus_pct FROM corporate_actions "
                       "WHERE book_close IS NOT NULL AND bonus_pct > 0", main)
main.close()
liquid = set(load()["symbol"])

# 1. calendar holes
days = pd.Series(sorted(long["trade_date"].unique()))
g = days.diff().dt.days
big = g > 4
print("calendar gaps longer than 4 days between trading days:")
print(pd.DataFrame({"after": days.shift(1)[big].dt.date, "next": days[big].dt.date,
                    "gap_days": g[big]}).to_string(index=False))

# 2. price gaps: the file's reference price vs the previous close
long["last_close"] = long.groupby("symbol")["close"].shift(1)
long["gap"] = (long["prev_close"] / long["last_close"] - 1) * 100
long["days_since"] = long.groupby("symbol")["trade_date"].diff().dt.days

# 3. announced bonuses vs the gap near the book close date
ca["book_close"] = pd.to_datetime(ca["book_close"])
ca = ca[(ca["book_close"] >= long["trade_date"].min()) & (ca["book_close"] <= long["trade_date"].max())]
by = {s: x for s, x in long.groupby("symbol")}
explained, ok_n, bad, nodata, offsets = set(), 0, [], 0, []
for _, r in ca.iterrows():
    x = by.get(r["symbol"])
    if x is None:
        nodata += 1
        continue
    w = x[(x["trade_date"] >= r["book_close"] - pd.Timedelta(days=1))
          & (x["trade_date"] <= r["book_close"] + pd.Timedelta(days=3)) & x["gap"].notna()]
    if w.empty:
        nodata += 1
        continue
    j = w["gap"].abs().idxmax()
    exp = -r["bonus_pct"] / (100 + r["bonus_pct"]) * 100
    if abs(w.at[j, "gap"] - exp) < 0.5:
        ok_n += 1
        explained.add((r["symbol"], w.at[j, "trade_date"]))
        offsets.append((w.at[j, "trade_date"] - r["book_close"]).days)
    else:
        bad.append((r["symbol"], r["book_close"].date(), r["bonus_pct"], round(exp, 2),
                    round(w.at[j, "gap"], 2)))
print(f"\nannounced bonus events in range: {len(ca)}")
print(f"  gap matches the announcement: {ok_n}   no price data near the date: {nodata}   "
      f"does not match: {len(bad)}")
print("  day offset of the matched gaps:", pd.Series(offsets).value_counts().sort_index().to_dict())
print("  examples that do not match (symbol, book close, bonus %, expected gap, actual gap):")
for b in bad[:10]:
    print("   ", b)

# 4. what are the gaps that no announcement explains?
e = long[long["symbol"].isin(eq) & (long["gap"].abs() > 0.5)].copy()
e["explained"] = [(s, d) in explained for s, d in zip(e["symbol"], e["trade_date"])]
for label, sub in [("equities, our window", e[e["trade_date"] >= lo]),
                   ("30 liquid stocks, all years", e[e["symbol"].isin(liquid)])]:
    print(f"\n{label}: {len(sub)} gaps over 0.5%, {int(sub['explained'].sum())} explained by a bonus")
    un = sub[~sub["explained"]]
    print("  unexplained by size of gap:",
          pd.cut(un["gap"].abs(), [0.5, 2, 5, 15, 1000]).value_counts().sort_index().to_dict())
    print("  median days since the stock's previous row:", un["days_since"].median())
print("\nlargest unexplained gaps among the 30 liquid stocks:")
top = e[e["symbol"].isin(liquid) & ~e["explained"]].copy()
top["abs"] = top["gap"].abs()
print(top.sort_values("abs", ascending=False).head(10)[
    ["trade_date", "symbol", "last_close", "prev_close", "close", "days_since"]].to_string(index=False))