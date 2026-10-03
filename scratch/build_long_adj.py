import os
import sqlite3

import pandas as pd

from app.config import DB_PATH

EXT = os.path.join(os.path.dirname(DB_PATH), "external.db")
ext = sqlite3.connect(EXT)
long = pd.read_sql_query(
    "SELECT trade_date, symbol, open, high, low, close, prev_close, volume, turnover "
    "FROM prices_long", ext)

main = sqlite3.connect(DB_PATH)
eq = set(pd.read_sql_query(
    "SELECT symbol FROM companies WHERE instrument_type = 'Equity'", main)["symbol"])
mine = pd.read_sql_query(
    "SELECT trade_date, symbol, adj_close AS adj_mine FROM prices WHERE volume > 0", main)
main.close()

long["trade_date"] = pd.to_datetime(long["trade_date"])
long = long[long["symbol"].isin(eq) & (long["close"] > 0) & (long["prev_close"] > 0)
            & (long["trade_date"] >= "2021-11-03")]
long = long.sort_values(["symbol", "trade_date"]).reset_index(drop=True)

g = long.groupby("symbol")
long["factor"] = (long["prev_close"] / g["close"].shift(1)).fillna(1.0)
long["days_since"] = g["trade_date"].diff().dt.days
long.loc[(long["factor"] - 1).abs() <= 0.005, "factor"] = 1.0      # ignore noise


def back_adjust(f):
    """multiplier for row t = product of the factors of all later rows"""
    return f[::-1].cumprod()[::-1].shift(-1).fillna(1.0)


long["mult"] = long.groupby("symbol")["factor"].transform(back_adjust)
for c in ("open", "high", "low", "close"):
    long[f"adj_{c}"] = long[c] * long["mult"]

applied = long[long["factor"] != 1.0]
print(f"{long['symbol'].nunique()} equities, {len(long)} rows, "
      f"{len(applied)} adjustments applied")
print("adjustments per year:", applied["trade_date"].dt.year.value_counts().sort_index().to_dict())
risky = applied[applied["days_since"] > 7]
print(f"adjustments right after a long break in the stock's rows (days_since > 7): {len(risky)}")
print("largest adjustments:")
top = applied.assign(size=(applied["factor"] - 1).abs()).sort_values("size", ascending=False).head(8)
print(top[["trade_date", "symbol", "factor", "days_since"]].to_string(index=False))

print("\nSBL spot check:")
s = long[(long["symbol"] == "SBL") & long["trade_date"].isin(
    pd.to_datetime(["2025-11-03", "2025-11-04", "2026-10-01", "2026-10-02"]))]
print(s[["trade_date", "close", "prev_close", "adj_close"]].to_string(index=False))

# validation: on the overlap window the ratio to our own adj_close should be about 1
long["d"] = long["trade_date"].dt.strftime("%Y-%m-%d")
m = long.merge(mine, left_on=["symbol", "d"], right_on=["symbol", "trade_date"],
               suffixes=("", "_m"))
m["ratio"] = m["adj_close"] / m["adj_mine"]
dev = (m["ratio"] - 1).abs()
print(f"\noverlap rows compared: {len(m)}")
print(f"within 0.5%: {(dev < 0.005).mean():.1%}   within 2%: {(dev < 0.02).mean():.1%}")
bad = m.assign(dev=dev).groupby("symbol")["dev"].max().sort_values(ascending=False)
print("symbols with the largest deviation (max abs ratio - 1):")
print(bad.head(10).round(3).to_string())
print(f"symbols with a deviation over 2%: {(bad > 0.02).sum()} of {len(bad)}")

out = long.copy()
out["trade_date"] = out["d"]
out[["trade_date", "symbol", "adj_open", "adj_high", "adj_low", "adj_close",
     "close", "volume", "turnover"]].to_sql("prices_long_adj", ext, if_exists="replace",
                                           index=False)
ext.close()
print("\nsaved prices_long_adj to external.db")