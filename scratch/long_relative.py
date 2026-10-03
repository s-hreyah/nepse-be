import sqlite3
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

DB = "data/external.db"
N_STOCKS, MIN_DAYS = 30, 900
HORIZONS = [5, 10, 20]

conn = sqlite3.connect(DB)
df = pd.read_sql_query(
    "SELECT trade_date, symbol, ret, turnover, flag_bonus FROM returns_final", conn)
conn.close()

counts = df.groupby("symbol").size()
eligible = counts[counts >= MIN_DAYS].index
med = df[df.symbol.isin(eligible)].groupby("symbol")["turnover"].median()
symbols = med.sort_values(ascending=False).head(N_STOCKS).index.tolist()
df = df[df.symbol.isin(symbols)].copy()

dates = sorted(df.trade_date.unique())
df["di"] = df.trade_date.map({d: i for i, d in enumerate(dates)})
df["g"] = (1 + df["ret"] / 100).clip(lower=1e-6)
df["flag"] = df["flag_bonus"].fillna(0).astype(int)
n = len(dates)

wide = df.pivot_table(index="di", columns="symbol", values="g", aggfunc="first").reindex(range(n))
logg = np.log(wide)
cnt = wide.notna().astype(int)
flg = df.pivot_table(index="di", columns="symbol", values="flag", aggfunc="max").reindex(range(n)).fillna(0)


def window(a, b):
    """return, row count and flag count per stock over date positions a..b-1"""
    ret = np.expm1(logg.iloc[a:b].sum())
    return ret, cnt.iloc[a:b].sum(), flg.iloc[a:b].sum()


def run(N, offset):
    rows = []
    for e in range(N + offset, n - N, N):
        pr, pc, pf = window(e - N + 1, e + 1)
        nr, nc, nf = window(e + 1, e + N + 1)
        ok = (pc > 0) & (nc > 0) & (pf == 0) & (nf == 0)
        if ok.sum() < 10:
            continue
        pe = pr[ok] - pr[ok].median()
        ne = nr[ok] - nr[ok].median()
        m = (pe != 0) & (ne != 0)
        if m.sum() < 10:
            continue
        hit = (np.sign(pe[m]) == np.sign(ne[m])).mean() * 100
        rho = spearmanr(pe, ne)[0]
        rows.append((dates[e][:4], hit, rho))
    return pd.DataFrame(rows, columns=["year", "hit", "rho"])


print(f"{len(symbols)} stocks, {n} trading dates in this panel\n")
for N in HORIZONS:
    for offset in (0, N // 2):
        r = run(N, offset)
        k = len(r)
        se_h = r.hit.std(ddof=1) / np.sqrt(k)
        se_r = r.rho.std(ddof=1) / np.sqrt(k)
        print(f"{N:>2}-day windows, offset {offset}: {k} dates | "
              f"momentum hit {r.hit.mean():.1f}% (SE {se_h:.1f}) | "
              f"rank corr {r.rho.mean():+.3f} (SE {se_r:.3f})")
    print(r.groupby("year").hit.agg(["count", "mean"]).round(1).T.to_string(), "\n")