import os
import sqlite3

import pandas as pd

from app.config import DB_PATH

EXT = os.path.join(os.path.dirname(DB_PATH), "external.db")
ext = sqlite3.connect(EXT)
df = pd.read_sql_query("SELECT * FROM sharesansar", ext)
df["trade_date"] = pd.to_datetime(df["trade_date"])

bad = df[(df["close"] <= 0) | (df["open"] <= 0) | (df["volume"] < 0)]
print("rows with zero or negative price or negative volume:")
print(bad[["trade_date", "symbol", "open", "close", "volume"]].to_string(index=False))
df = df.drop(bad.index)

# drop non-trading days: a file identical to the previous one in close and volume
pc = df.pivot_table(index="trade_date", columns="symbol", values="close")
pv = df.pivot_table(index="trade_date", columns="symbol", values="volume")
keep = [pc.index[0]]
for i in range(1, len(pc)):
    same = pc.iloc[i].equals(pc.iloc[i - 1]) and pv.iloc[i].equals(pv.iloc[i - 1])
    if not same:
        keep.append(pc.index[i])
long = df[df["trade_date"].isin(keep)].copy()
days = pd.Series(sorted(long["trade_date"].unique()))
print(f"\n{len(days)} distinct trading days from {days.iloc[0].date()} to {days.iloc[-1].date()}")
print(days.dt.year.value_counts().sort_index().to_string())

main = sqlite3.connect(DB_PATH)
ours = pd.to_datetime(pd.read_sql_query("SELECT DISTINCT trade_date FROM prices", main)["trade_date"])
comp = pd.read_sql_query("SELECT symbol, instrument_type FROM companies", main)
main.close()

lo = ours.min()
mine = set(days[days >= lo])
theirs = set(ours)
print(f"\nIn the overlap window: ours {len(theirs)} days, theirs {len(mine)} days")
print("in ours but not theirs:", sorted(d.date().isoformat() for d in theirs - mine)[:10])
print("in theirs but not ours:", sorted(d.date().isoformat() for d in mine - theirs)[:10])

syms = set(long["symbol"])
known = set(comp["symbol"])
print(f"\nsymbols in the long data: {len(syms)}; not in our companies table: {len(syms - known)}")
print("examples:", sorted(syms - known)[:15])

# adjustment events: reference price differs from the previous close
long = long.sort_values(["symbol", "trade_date"])
long["gap_pct"] = (long["prev_close"] / long.groupby("symbol")["close"].shift(1) - 1) * 100
ev = long[long["gap_pct"].abs() > 0.5]
print(f"\nadjustment-like events (reference price differs by over 0.5%): {len(ev)}")
print(ev["trade_date"].dt.year.value_counts().sort_index().to_string())
print("window since our first date:", int((ev["trade_date"] >= lo).sum()),
      "(compare with your 124, which may count different securities)")

long["trade_date"] = long["trade_date"].dt.strftime("%Y-%m-%d")
long.to_sql("prices_long", ext, if_exists="replace", index=False)
ext.close()
print("\nsaved", len(long), "rows to prices_long in external.db")