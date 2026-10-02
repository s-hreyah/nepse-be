import time
import pandas as pd
from nepse_data_api import Nepse

from app.db import get_connection
from jobs.forecast_vol import load

try:
    import nepali_datetime
except ImportError:
    nepali_datetime = None


def to_ad(s):
    """Structured dates come as AD or Bikram Sambat (year above 2050)."""
    if not s:
        return None
    try:
        y, m, d = (int(x) for x in str(s)[:10].split("-"))
        if y < 2050:
            return f"{y:04d}-{m:02d}-{d:02d}"
        return nepali_datetime.date(y, m, d).to_datetime_date().isoformat()
    except Exception:
        return None

def fetch_agm(n, sym):
    """Retry with a fresh session; returns (client, items or None)."""
    for attempt in range(3):
        try:
            return n, n.get_agm(sym)
        except Exception:
            time.sleep(5 * (attempt + 1))
            n = Nepse()
    return n, None


def ingest(all_equities=False):
    if all_equities:
        conn = get_connection()
        symbols = [r[0] for r in conn.execute(
            "SELECT symbol FROM companies WHERE instrument_type = 'Equity'")]
        conn.close()
    else:
        symbols = load()["symbol"].unique().tolist()

    n = Nepse()
    rows, done, failed = [], [], []
    for i, sym in enumerate(symbols):
        if i and i % 40 == 0:
            n = Nepse()                          # fresh session every 40 calls
        n, items = fetch_agm(n, sym)
        if items is None:
            failed.append(sym)
            continue
        done.append(sym)
        for it in items:
            cn = it.get("companyNews") or {}
            a = cn.get("agmNotice") or {}
            rows.append((sym, to_ad(a.get("bookCloseDate")), a.get("bookCloseDate"),
                         to_ad(a.get("agmDate")), a.get("cashDividend"), a.get("bonusShare"),
                         (cn.get("addedDate") or "")[:10]))
        time.sleep(1.5)

    df = pd.DataFrame(rows, columns=["symbol", "book_close", "book_close_raw", "agm_date",
                                     "cash_pct", "bonus_pct", "added_date"])
    df = df[df["book_close"].isna() | (df["book_close"] >= "2015-01-01")]
    df = df.drop_duplicates(subset=["symbol", "book_close"])

    conn = get_connection()
    conn.execute("CREATE TABLE IF NOT EXISTS corporate_actions (symbol TEXT, book_close TEXT, "
                 "book_close_raw TEXT, agm_date TEXT, cash_pct REAL, bonus_pct REAL, added_date TEXT)")
    conn.executemany("DELETE FROM corporate_actions WHERE symbol = ?", [(s,) for s in done])
    df.to_sql("corporate_actions", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()
    print(f"{len(done)} stocks fetched, {len(failed)} failed, {len(df)} events saved")
    if failed:
        print("failed:", " ".join(failed))


def check():
    conn = get_connection()
    ev = pd.read_sql_query("SELECT * FROM corporate_actions WHERE book_close IS NOT NULL", conn)
    px = pd.read_sql_query("SELECT symbol, trade_date, close, prev_close, pct_change FROM prices "
                           "WHERE volume > 0 ORDER BY symbol, trade_date", conn)
    conn.close()
    px["gap"] = (px["prev_close"] / px.groupby("symbol")["close"].shift(1) - 1) * 100

    res = []
    for _, e in ev.iterrows():
        g = px[px["symbol"] == e["symbol"]].reset_index(drop=True)
        if g.empty or not (g["trade_date"].min() <= e["book_close"] <= g["trade_date"].max()):
            continue
        i = g.index[g["trade_date"] >= e["book_close"]][0]
        win = g.iloc[max(i - 3, 0): i + 4].dropna(subset=["gap"])
        j = win["gap"].abs().idxmax() if len(win) else None
        bonus = e["bonus_pct"] or 0
        res.append({
            "symbol": e["symbol"], "book_close": e["book_close"],
            "cash": e["cash_pct"], "bonus": bonus,
            "gap_offset": (j - i) if j is not None and abs(g.at[j, "gap"]) > 0.5 else None,
            "gap": round(g.at[j, "gap"], 2) if j is not None else None,
            "expected_gap": round(-bonus / (100 + bonus) * 100, 2),
            "cash_drag": round(-(e["cash_pct"] or 0) / g.at[i, "prev_close"] * 100, 2) if g.at[
                i, "prev_close"] else None,
            "pct_on_day": g.at[i, "pct_change"],
        })
    r = pd.DataFrame(res)
    print(f"\n{len(r)} events fall inside the price window")
    if r.empty:
        return
    print(r.to_string(index=False))
    b = r[r["bonus"] > 0]
    bad = b[(b["gap"] - b["expected_gap"]).abs() > 0.3]
    print(f"\nBonus events where the price gap differs from the announced bonus by more than 0.3 points: {len(bad)} of {len(b)}")
    if len(bad):
        print(bad[["symbol", "book_close", "bonus", "gap", "expected_gap", "gap_offset"]].to_string(index=False))
    print("\nBonus events: trading-day offset of the price adjustment from the book close date")
    print(b["gap_offset"].value_counts(dropna=False).sort_index().to_string())
    c = r[(r["bonus"] == 0) & (r["cash"] > 0)]
    if len(c):
        print(f"\nCash-only events: {len(c)}, average move on the book close day "
              f"{c['pct_on_day'].mean():.2f}%, share of days down {(c['pct_on_day'] < 0).mean():.0%}")


if __name__ == "__main__":
    ingest()
    check()