import pandas as pd
from app.db import get_connection


def run():
    conn = get_connection()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(prices)")}
    if "adj_close" not in cols:
        conn.execute("ALTER TABLE prices ADD COLUMN adj_close REAL")

    df = pd.read_sql_query(
        "SELECT trade_date, symbol, close, prev_close FROM prices ORDER BY symbol, trade_date",
        conn)

    updates, events = [], 0
    for sym, g in df.groupby("symbol"):
        g = g.sort_values("trade_date").reset_index(drop=True)
        lag = g["close"].shift(1)
        ratio = g["prev_close"] / lag
        valid = (ratio.notna() & (g["close"] > 0) & (g["prev_close"] > 0) & (lag > 0)
                 & ((ratio - 1).abs() > 0.01))
        ratio = ratio.where(valid, 1.0)
        events += int(valid.sum())

        # factor for day t = product of the ratios of all LATER days
        later = ratio[::-1].cumprod()[::-1].shift(-1).fillna(1.0)
        adj = g["close"] * later
        for d, a in zip(g["trade_date"], adj):
            updates.append((None if pd.isna(a) else float(a), d, sym))

    conn.executemany(
        "UPDATE prices SET adj_close = ? WHERE trade_date = ? AND symbol = ?", updates)
    conn.commit()
    print(f"Updated {len(updates)} rows, {events} adjustment events found\n")

    print("NLO around its adjustment (close vs adj_close):")
    for r in conn.execute(
        "SELECT trade_date, close, adj_close, pct_change FROM prices "
        "WHERE symbol='NLO' AND trade_date BETWEEN '2026-09-21' AND '2026-09-28' "
        "ORDER BY trade_date"):
        print(r)
    conn.close()


if __name__ == "__main__":
    run()