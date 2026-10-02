from app.db import get_connection


def run():
    conn = get_connection()
    q = lambda sql: conn.execute(sql).fetchall()
    problems = 0

    days = q("SELECT trade_date, COUNT(*) FROM prices GROUP BY trade_date ORDER BY trade_date")
    counts = sorted(n for _, n in days)
    median = counts[len(counts) // 2]
    thin = [(d, n) for d, n in days if n < 0.8 * median]
    print(f"Days stored: {len(days)}, latest {days[-1][0]}, median rows/day {median}")
    print(f"Days with under 80% of the usual row count: {len(thin)}", thin[:5])
    problems += len(thin)

    bad = q("SELECT trade_date, symbol, close FROM prices WHERE volume > 0 AND (close IS NULL OR close <= 0)")
    print("Traded rows with a missing or zero close:", len(bad), bad[:5])
    problems += len(bad)

    bad = q("""SELECT trade_date, symbol, low, close, high FROM prices
               WHERE volume > 0 AND (high < low OR close > high + 0.01 OR close < low - 0.01)""")
    print("Rows where close is outside the day's low-high range:", len(bad), bad[:5])
    problems += len(bad)

    bad = q("SELECT trade_date, symbol, pct_change FROM prices WHERE volume > 0 AND ABS(pct_change) > 15.5")
    print("Moves beyond the 15% limit:", len(bad), bad[:5])
    problems += len(bad)

    bad = q("SELECT COUNT(*) FROM prices WHERE adj_close IS NULL")[0][0]
    print("Rows without an adjusted close:", bad)
    problems += bad

    conn.close()
    print("\nAll checks passed" if problems == 0 else f"\n{problems} issues found")


if __name__ == "__main__":
    run()