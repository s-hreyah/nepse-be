import os
import sqlite3

import pandas as pd

from app.config import DB_PATH

EXT = os.path.join(os.path.dirname(DB_PATH), "external.db")
ext = sqlite3.connect(EXT)
r = pd.read_sql_query("SELECT * FROM returns_clean", ext)
r["date"] = pd.to_datetime(r["trade_date"])

main = sqlite3.connect(DB_PATH)
ca = pd.read_sql_query(
    "SELECT symbol, book_close, bonus_pct FROM corporate_actions "
    "WHERE book_close IS NOT NULL AND bonus_pct >= 5", main)
main.close()
ca["bc"] = pd.to_datetime(ca["book_close"])
ca = ca[(ca["bc"] >= r["date"].min()) & (ca["bc"] <= r["date"].max())]
ca = ca.drop_duplicates(["symbol", "bc"])
by = {s: g for s, g in r.groupby("symbol")}

out, flag_idx = [], []
for _, e in ca.iterrows():
    g = by.get(e["symbol"])
    if g is None:
        continue
    w = g[(g["date"] >= e["bc"]) & (g["date"] <= e["bc"] + pd.Timedelta(days=3))]
    if w.empty:
        continue
    exp = -e["bonus_pct"] / (100 + e["bonus_pct"]) * 100
    j = w["ret"].idxmin()
    bad = bool(w.at[j, "ret"] < exp / 2)      # the drop is still inside the return
    if bad:
        flag_idx.append(j)
    out.append({"symbol": e["symbol"], "book_close": e["book_close"], "bonus": e["bonus_pct"],
                "expected": round(exp, 2), "worst_ret": round(w.at[j, "ret"], 2),
                "year": e["book_close"][:4], "flagged": bad})
res = pd.DataFrame(out)

print(f"bonus events of 5% or more with price data in the window: {len(res)}")
print(f"  return looks adjusted: {int((~res['flagged']).sum())}")
print(f"  return still contains the bonus drop: {int(res['flagged'].sum())}")
print("\nflagged events by year:")
print(res.groupby("year")["flagged"].agg(flagged="sum", events="count").to_string())
print(f"\naverage worst return in the window, adjusted events: "
      f"{res[~res['flagged']]['worst_ret'].mean():.2f}%")
print("\nexamples of flagged events:")
print(res[res["flagged"]].head(12).to_string(index=False))

r["flag_bonus"] = False
r.loc[flag_idx, "flag_bonus"] = True
r.drop(columns="date").to_sql("returns_final", ext, if_exists="replace", index=False)
ext.close()
print(f"\nsaved returns_final: {len(r)} rows, {len(flag_idx)} stock-days flagged")