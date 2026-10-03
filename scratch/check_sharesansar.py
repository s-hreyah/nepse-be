import glob
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

from app.config import DB_PATH

SRC = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1
                         else "~/Desktop/external/sharesansar_datascrape/data")
NUM = ["Open", "High", "Low", "Close", "Vol", "Prev. Close", "Turnover", "Trans."]
COLS = ["Symbol"] + NUM

files = sorted(glob.glob(os.path.join(SRC, "*.csv")))
print(len(files), "files")

first = [int(os.path.basename(f).split("_")[0]) for f in files]
second = [int(os.path.basename(f).split("_")[1]) for f in files]
print("largest 1st part:", max(first), "| largest 2nd part:", max(second))
fmt = "%d_%m_%Y" if max(first) > 12 else "%m_%d_%Y"
print("reading dates as", "day_month_year" if fmt.startswith("%d") else "month_day_year")

parts = []
for f in files:
    d = pd.to_datetime(os.path.basename(f)[:-4], format=fmt)
    df = pd.read_csv(f).reindex(columns=COLS)
    for c in NUM:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "", regex=False), errors="coerce")
    df["file_date"] = d
    parts.append(df)
all_ = pd.concat(parts, ignore_index=True)

dates = pd.Series(sorted(all_["file_date"].unique()))
print("\ndate range:", dates.iloc[0].date(), "to", dates.iloc[-1].date())
print("files per year:")
print(dates.dt.year.value_counts().sort_index().to_string())
print("\nfiles by weekday (Mon=0 ... Fri=4, Sat=5, Sun=6):")
print(dates.dt.weekday.value_counts().sort_index().to_string())
rows = all_.groupby("file_date").size()
print(f"\nrows per file: min {rows.min()}, median {int(rows.median())}, max {rows.max()}")

piv = all_.pivot_table(index="file_date", columns="Symbol", values="Close")
dup = piv.sub(piv.shift()).abs().max(axis=1) == 0
print(f"\nfiles identical to the previous file: {int(dup.sum())}")
print([d.date().isoformat() for d in piv.index[dup][:8]])

bad = all_[(all_["Close"] <= 0) | (all_["Open"] <= 0) | (all_["Vol"] < 0)]
print(f"rows with zero or negative price or negative volume: {len(bad)}")

conn = sqlite3.connect(DB_PATH)
db = pd.read_sql_query("SELECT trade_date, symbol, close FROM prices", conn)
conn.close()
db["trade_date"] = pd.to_datetime(db["trade_date"])
dbp = db.pivot_table(index="trade_date", columns="symbol", values="close")

res = []
for f in piv.index:
    if f < dbp.index.min() - pd.Timedelta(days=3):
        continue
    best = (None, np.nan)
    for c in dbp.index[np.abs((dbp.index - f).days) <= 3]:
        a, b = piv.loc[f], dbp.loc[c]
        both = a.notna() & b.notna()
        if both.sum() < 100:
            continue
        r = ((a[both] - b[both]).abs() < 0.01).mean()
        if np.isnan(best[1]) or r > best[1]:
            best = (c, r)
    res.append((f, best[0], best[1]))
r = pd.DataFrame(res, columns=["file_date", "db_date", "match"])
r["offset_days"] = (r["db_date"] - r["file_date"]).dt.days
print(f"\n{len(r)} file dates overlap our database window")
print("day offset between a file's date and the NEPSE date its numbers match:")
print(r["offset_days"].value_counts(dropna=False).sort_index().to_string())
print(f"close match rate: median {r['match'].median():.3f}, "
      f"files above 0.95: {(r['match'] > 0.95).sum()} of {len(r)}")
print(r[r["match"] < 0.95].head(8).to_string(index=False))

out = sqlite3.connect(os.path.join(os.path.dirname(DB_PATH), "external.db"))
save = all_.rename(columns={"file_date": "trade_date", "Symbol": "symbol", "Open": "open",
                            "High": "high", "Low": "low", "Close": "close", "Vol": "volume",
                            "Prev. Close": "prev_close", "Turnover": "turnover", "Trans.": "trans"})
save["trade_date"] = save["trade_date"].dt.strftime("%Y-%m-%d")
save.to_sql("sharesansar", out, if_exists="replace", index=False)
out.close()
print("\nsaved", len(save), "rows to data/external.db")