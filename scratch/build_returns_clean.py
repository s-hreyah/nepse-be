import os
import sqlite3

import pandas as pd

from app.config import DB_PATH

EXT = os.path.join(os.path.dirname(DB_PATH), "external.db")
ext = sqlite3.connect(EXT)
r = pd.read_sql_query(
    "SELECT trade_date, symbol, ret, close, volume, turnover FROM returns_long", ext)
r["prev_close"] = r["close"] / (1 + r["ret"] / 100)

# 1. missed trading days: median across stocks of (reference price / last file's close - 1)
close = r.pivot_table(index="trade_date", columns="symbol", values="close")
prev = r.pivot_table(index="trade_date", columns="symbol", values="prev_close")
gap = prev / close.shift(1) - 1
cal = pd.DataFrame({
    "days_since_prev_file": pd.to_datetime(close.index.to_series()).diff().dt.days,
    "stocks_used": gap.notna().sum(axis=1),
    "median_gap_pct": (gap.median(axis=1) * 100).round(2)})
cal = cal[cal["stocks_used"] >= 30]
show = cal[(cal["days_since_prev_file"] > 4) | (cal["median_gap_pct"].abs() > 0.2)]
print("calendar holes (over 4 days) and dates where the market moved between files:")
print(show.to_string())
breaks = cal[cal["median_gap_pct"].abs() > 0.2]
print(f"\n{len(breaks)} dates look like missed trading days (median gap over 0.2%)")

# 2. the daily limit: first date with several stocks above 10.5%
big = r[r["ret"].abs() > 10.5]
cnt = big.groupby("trade_date").size()
change = cnt[cnt >= 3].index.min()
print(f"\nlimit change looks to be around: {change}")
print("returns beyond 10.5% by month (last 14 months with any):")
print(big.assign(month=big["trade_date"].str[:7]).groupby("month").size().tail(14).to_string())

# 3. drop impossible rows
before = r["trade_date"] < change
bad = (before & (r["ret"].abs() > 10.5)) | (~before & (r["ret"].abs() > 15.5))
print(f"\ndropping {int(bad.sum())} rows beyond the limit of their period:")
print(r[bad][["trade_date", "symbol", "ret"]].round(2).to_string(index=False))
clean = r[~bad].copy()
clean["after_break"] = clean["trade_date"].isin(breaks.index)
clean[["trade_date", "symbol", "ret", "close", "volume", "turnover", "after_break"]].to_sql(
    "returns_clean", ext, if_exists="replace", index=False)
breaks.reset_index().to_sql("calendar_breaks", ext, if_exists="replace", index=False)
ext.close()
print(f"\nsaved returns_clean ({len(clean)} rows) and calendar_breaks to external.db")