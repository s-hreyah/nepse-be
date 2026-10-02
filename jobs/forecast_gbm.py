import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from app.db import get_connection

TOP_N, MIN_SHARE, START, STEP = 30, 0.95, 120, 10

conn = get_connection()
df = pd.read_sql_query(
    "SELECT p.trade_date, p.symbol, p.adj_close, p.volume, p.turnover "
    "FROM prices p JOIN companies c ON c.symbol = p.symbol "
    "WHERE c.instrument_type = 'Equity' ORDER BY p.symbol, p.trade_date", conn)
idx = pd.read_sql_query(
    "SELECT trade_date, close FROM indices WHERE index_id = 58 ORDER BY trade_date", conn)
conn.close()

idx["idx_ret1"] = idx["close"].pct_change() * 100
idx["idx_ret5"] = idx["close"].pct_change(5) * 100
idx = idx[["trade_date", "idx_ret1", "idx_ret5"]]

n_days = df["trade_date"].nunique()
t = df[df["volume"] > 0].groupby("symbol").agg(days=("trade_date", "nunique"),
                                              med=("turnover", "median"))
liquid = t[t["days"] / n_days >= MIN_SHARE].sort_values("med", ascending=False).head(TOP_N)


def rsi(p, n=14):
    d = p.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


parts = []
for sym in liquid.index:
    s = df[(df["symbol"] == sym) & (df["volume"] > 0)].reset_index(drop=True)
    p = s["adj_close"]
    r = p.pct_change() * 100
    parts.append(pd.DataFrame({
        "symbol": sym, "trade_date": s["trade_date"],
        "ret1": r, "ret2": r.shift(1), "ret3": r.shift(2),
        "ret5": p.pct_change(5) * 100, "ret20": p.pct_change(20) * 100,
        "vol5": r.rolling(5).std(), "vol20": r.rolling(20).std(),
        "dist_ma20": (p / p.rolling(20).mean() - 1) * 100,
        "dist_ma50": (p / p.rolling(50).mean() - 1) * 100,
        "rsi14": rsi(p),
        "vol_ratio": s["volume"] / s["volume"].rolling(20).mean(),
        "target": r.shift(-1),                      # next day's return
    }))
panel = pd.concat(parts, ignore_index=True).merge(idx, on="trade_date", how="left")
FEATS = [c for c in panel.columns if c not in ("symbol", "trade_date", "target")]

dates = sorted(panel["trade_date"].unique())
out = []
for b, i in enumerate(range(START, len(dates), STEP)):
    train = panel[(panel["trade_date"] < dates[i]) & panel["target"].notna()]
    test = panel[panel["trade_date"].isin(dates[i:i + STEP]) & panel["target"].notna()]
    if test.empty:
        continue
    m = HistGradientBoostingRegressor(loss="absolute_error", max_depth=3,
                                      learning_rate=0.05, max_iter=150,
                                      min_samples_leaf=50, random_state=0)
    m.fit(train[FEATS], train["target"])
    out.append(test.assign(pred=m.predict(test[FEATS]), block=b, n_train=len(train)))
res = pd.concat(out, ignore_index=True)
print(f"{len(res)} out-of-sample predictions, first block trained on {out[0]['n_train'].iloc[0]} rows\n")

mae_m = (res["target"] - res["pred"]).abs().mean()
mae_n = res["target"].abs().mean()
print(f"MAE  model {mae_m:.3f}   naive {mae_n:.3f}   ratio {mae_m / mae_n:.3f}  (below 1.0 beats naive)")

up_actual = res["target"] > 0
up_pred = res["pred"] > 0
print(f"\nDirection: model {(up_pred == up_actual).mean() * 100:.1f}% correct, "
      f"always down {(~up_actual).mean() * 100:.1f}%")
print(f"Model predicts 'up' on {up_pred.mean() * 100:.1f}% of days")
print(f"Correlation of prediction with actual: {res['pred'].corr(res['target']):.3f}")

res["ae_m"] = (res["target"] - res["pred"]).abs()
res["ae_n"] = res["target"].abs()
per = res.groupby("block")[["ae_m", "ae_n"]].mean()
per["ratio"] = (per["ae_m"] / per["ae_n"]).round(3)
print("\nRatio to naive by 10-day block (stable or one lucky block?):")
print(per["ratio"].to_string())