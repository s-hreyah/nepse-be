import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LinearRegression

from app.db import get_connection

N_STOCKS = 30
START = 120        # first test row per stock
REFIT = 20         # refit the model every 20 test dates
Z80 = 1.2816       # 80% band for a normal distribution
SIGMA_PER_MAE = 1.2533   # for a normal distribution, sigma = 1.2533 x mean absolute move
FEATS = ["a", "m5", "m20", "m60"]


def load():
    conn = get_connection()
    liquid = pd.read_sql_query(
        """SELECT p.symbol, COUNT(*) AS days, SUM(p.turnover) AS turnover
           FROM prices p JOIN companies c ON c.symbol = p.symbol
           WHERE c.instrument_type = 'Equity' AND p.volume > 0
           GROUP BY p.symbol ORDER BY days DESC, turnover DESC LIMIT ?""",
        conn, params=(N_STOCKS,))
    symbols = liquid["symbol"].tolist()
    marks = ",".join("?" * len(symbols))
    px = pd.read_sql_query(
        f"SELECT trade_date, symbol, adj_close FROM prices "
        f"WHERE symbol IN ({marks}) AND adj_close > 0 ORDER BY symbol, trade_date",
        conn, params=symbols)
    conn.close()
    return px


def build(px):
    parts = []
    for sym, g in px.groupby("symbol"):
        g = g.sort_values("trade_date").reset_index(drop=True)
        r = g["adj_close"].pct_change() * 100
        a = r.abs()
        parts.append(pd.DataFrame({
            "symbol": sym,
            "date": g["trade_date"],
            "pos": range(len(g)),
            "a": a,                                   # today's absolute move
            "m5": a.rolling(5).mean(),
            "m20": a.rolling(20).mean(),
            "m60": a.rolling(60).mean(),
            "ewma": a.ewm(alpha=0.06, adjust=False).mean(),
            "y": a.shift(-1),                         # tomorrow's absolute move (the target)
            "r_next": r.shift(-1),
            "target_date": g["trade_date"].shift(-1),
        }))
    df = pd.concat(parts, ignore_index=True)
    return df.dropna(subset=["a", "m5", "m20", "m60", "ewma", "y", "target_date"]).reset_index(drop=True)


def walk_forward(df):
    test = df[df["pos"] >= START].copy()
    dates = sorted(test["date"].unique())
    test["model"] = np.nan
    for i in range(0, len(dates), REFIT):
        chunk = dates[i:i + REFIT]
        train = df[df["target_date"] < chunk[0]]      # only outcomes already known
        if len(train) < 500:
            continue
        lr = LinearRegression().fit(train[FEATS], train["y"])
        idx = test["date"].isin(chunk)
        test.loc[idx, "model"] = lr.predict(test.loc[idx, FEATS])
    return test.dropna(subset=["model"])


def report(t):
    methods = {"yesterday": "a", "avg 5d": "m5", "avg 20d": "m20",
               "avg 60d": "m60", "EWMA": "ewma", "linear model": "model"}
    base = (t["m20"] - t["y"]).abs().mean()
    n_stocks = t["symbol"].nunique()
    print(f"Test rows: {len(t)}, stocks: {n_stocks}, dates: {t['date'].min()} to {t['date'].max()}")
    print(f"Average real absolute move: {t['y'].mean():.2f}%\n")
    print(f"{'method':13}{'MAE':>7}{'vs 20d':>8}{'rank corr':>11}{'beats 20d':>11}{'80% band':>10}")

    for name, col in methods.items():
        mae = (t[col] - t["y"]).abs().mean()
        rhos, wins = [], 0
        for _, g in t.groupby("symbol"):
            rho = spearmanr(g[col], g["y"])[0]
            if not np.isnan(rho):
                rhos.append(rho)
            wins += (g[col] - g["y"]).abs().mean() < (g["m20"] - g["y"]).abs().mean()
        half = Z80 * SIGMA_PER_MAE * t[col]
        hit = (t["r_next"].abs() <= half).mean()
        print(f"{name:13}{mae:7.3f}{mae / base:8.3f}{np.mean(rhos):11.3f}"
              f"{str(wins) + '/' + str(n_stocks):>11}{hit:9.1%}")


def blocks(t, k=5):
    dates = sorted(t["date"].unique())
    size = len(dates) // k
    print("\nEWMA vs 20d by time block (below 1.0 means EWMA is better)")
    for i in range(k):
        chunk = dates[i * size:(i + 1) * size] if i < k - 1 else dates[i * size:]
        b = t[t["date"].isin(chunk)]
        ratio = (b["ewma"] - b["y"]).abs().mean() / (b["m20"] - b["y"]).abs().mean()
        print(f"{chunk[0]} to {chunk[-1]}: {ratio:.3f}")

def calibrate(t):
    dates = sorted(t["date"].unique())
    cut = dates[len(dates) // 2]
    first, second = t[t["date"] < cut], t[t["date"] >= cut]
    print("\n80% band: multiplier fitted on the first half, checked on the second")
    for name, col in [("avg 20d", "m20"), ("EWMA", "ewma")]:
        ratio = (first["r_next"].abs() / first[col]).replace([np.inf, -np.inf], np.nan).dropna()
        k = ratio.quantile(0.8)
        hit1 = (first["r_next"].abs() <= k * first[col]).mean()
        hit2 = (second["r_next"].abs() <= k * second[col]).mean()
        print(f"{name:8} multiplier {k:.2f}   first half {hit1:.1%}   second half {hit2:.1%}")

if __name__ == "__main__":
    px = load()
    df = build(px)
    test = walk_forward(df)
    report(test)
    blocks(test)
    calibrate(test)
