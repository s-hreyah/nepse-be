import os
import sqlite3

import pandas as pd

from app.config import DB_PATH

EXT = os.path.join(os.path.dirname(DB_PATH), "external.db")
ext = sqlite3.connect(EXT)
long = pd.read_sql_query(
    "SELECT trade_date, symbol, close, prev_close, volume, turnover FROM prices_long", ext)

main = sqlite3.connect(DB_PATH)
eq = set(pd.read_sql_query(
    "SELECT symbol FROM companies WHERE instrument_type = 'Equity'", main)["symbol"])
mine = pd.read_sql_query(
    "SELECT trade_date, symbol, adj_close FROM prices WHERE volume > 0 "
    "ORDER BY symbol, trade_date", main)
main.close()

long = long[long["symbol"].isin(eq) & (long["close"] > 0) & (long["prev_close"] > 0)
            & (long["volume"] > 0) & (long["trade_date"] >= "2021-11-03")].copy()
long["ret"] = (long["close"] / long["prev_close"] - 1) * 100
long = long.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
long["year"] = long["trade_date"].str[:4]
print(f"{long['symbol'].nunique()} equities, {len(long)} stock-days")

print("\ndaily returns beyond 10.5% and beyond 15.5%, by year (the limit has changed over time):")
print(pd.DataFrame({
    "over_10.5": long[long["ret"].abs() > 10.5].groupby("year").size(),
    "over_15.5": long[long["ret"].abs() > 15.5].groupby("year").size()}).fillna(0).astype(int))
print("largest absolute returns:")
top = long.assign(a=long["ret"].abs()).sort_values("a", ascending=False).head(8)
print(top[["trade_date", "symbol", "close", "prev_close", "ret"]].round(2).to_string(index=False))

print("\nSBL on its book close days (known truth: -1.29% and -2.41%):")
s = long[(long["symbol"] == "SBL") & long["trade_date"].isin(["2025-11-03", "2026-10-02"])]
print(s[["trade_date", "close", "prev_close", "ret"]].round(2).to_string(index=False))

mine["my_ret"] = mine.groupby("symbol")["adj_close"].pct_change() * 100
m = long.merge(mine[["trade_date", "symbol", "my_ret"]], on=["trade_date", "symbol"]).dropna(
    subset=["my_ret"])
d = m["ret"] - m["my_ret"]
print(f"\nagainst our own adj_close returns: {len(m)} stock-days compared")
print(f"within 0.1 points: {(d.abs() < 0.1).mean():.1%}   within 0.5 points: {(d.abs() < 0.5).mean():.1%}")
print(f"disagreements over 2 points: {int((d.abs() > 2).sum())} "
      f"(file return lower: {int((d < -2).sum())}, higher: {int((d > 2).sum())})")
m["diff"] = d
print("largest disagreements (ret = from the file, my_ret = from our adj_close):")
print(m.reindex(d.abs().sort_values(ascending=False).index).head(10)[
    ["trade_date", "symbol", "ret", "my_ret"]].round(2).to_string(index=False))

n = long.groupby("symbol").size()
print(f"\nsymbols with 900 or more trading days: {(n >= 900).sum()}, "
      f"with 600 or more: {(n >= 600).sum()}")

long["idx"] = long.groupby("symbol")["ret"].transform(lambda r: 100 * (1 + r / 100).cumprod())
long[["trade_date", "symbol", "ret", "idx", "close", "volume", "turnover"]].to_sql(
    "returns_long", ext, if_exists="replace", index=False)
ext.close()
print("\nsaved returns_long to external.db")