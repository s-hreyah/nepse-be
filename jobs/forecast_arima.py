import warnings
import numpy as np
from statsmodels.tsa.arima.model import ARIMA

from jobs.forecast_vol import load, START, REFIT

warnings.filterwarnings("ignore")
ORDER = (1, 0, 1)


def predict_stock(r):
    """One-step-ahead return predictions; each uses only earlier days."""
    preds = np.full(len(r), np.nan)
    for s in range(START, len(r), REFIT):
        e = min(s + REFIT, len(r))
        try:
            res = ARIMA(r[:s], order=ORDER).fit()
            ext = res.append(r[s:e], refit=False)     # parameters stay fixed
            preds[s:e] = ext.fittedvalues[-(e - s):]
        except Exception:
            continue
    return preds


def run():
    px = load()
    err_a, err_n = [], []
    wins = n_stocks = correct = total = down = up = 0

    for sym, g in px.groupby("symbol"):
        g = g.sort_values("trade_date")
        r = (g["adj_close"].pct_change() * 100).dropna().to_numpy()
        p = predict_stock(r)
        ok = ~np.isnan(p)
        if ok.sum() < 30:
            continue
        y, p = r[ok], p[ok]
        err_a.append(np.abs(y - p))
        err_n.append(np.abs(y))                        # naive: predict no change
        n_stocks += 1
        wins += np.abs(y - p).mean() < np.abs(y).mean()
        nz = y != 0
        correct += (np.sign(p[nz]) == np.sign(y[nz])).sum()
        total += nz.sum()
        down += (y[nz] < 0).sum()
        up += (y[nz] > 0).sum()

    ea, en = np.concatenate(err_a), np.concatenate(err_n)
    print(f"Stocks: {n_stocks}, test rows: {len(ea)}")
    print(f"MAE ARIMA{ORDER}: {ea.mean():.3f}   naive (no change): {en.mean():.3f}   ratio {ea.mean() / en.mean():.3f}")
    print(f"ARIMA beats naive on {wins}/{n_stocks} stocks")
    print(f"Direction: ARIMA {correct / total:.1%}   always down {down / total:.1%}   always up {up / total:.1%}")


if __name__ == "__main__":
    run()