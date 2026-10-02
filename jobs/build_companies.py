from collections import Counter

from nepse_data_api import Nepse
from app.db import get_connection


def run():
    data = Nepse().get_company_list()
    if not data:
        print("No companies returned, nothing saved")
        return

    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            symbol TEXT PRIMARY KEY,
            name TEXT,
            sector TEXT,
            instrument_type TEXT,
            status TEXT
        )
    """)
    for c in data:
        conn.execute(
            "INSERT OR REPLACE INTO companies (symbol, name, sector, instrument_type, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (c.get("symbol"), c.get("companyName"), c.get("sectorName"),
             c.get("instrumentType"), c.get("status")),
        )
    conn.commit()

    print(f"Saved {len(data)} companies\n")
    print("Instrument types:", Counter(c.get("instrumentType") for c in data).most_common())
    print("\nSectors:")
    for s, n in Counter(c.get("sectorName") for c in data).most_common():
        print(f"  {n:4}  {s}")

    # How well do company symbols cover what actually trades?
    latest = conn.execute("SELECT MAX(trade_date) FROM prices").fetchone()[0]
    unmatched = conn.execute(
        """SELECT p.symbol, p.name FROM prices p
           LEFT JOIN companies c ON c.symbol = p.symbol
           WHERE p.trade_date = ? AND c.symbol IS NULL
           ORDER BY p.turnover DESC""", (latest,)).fetchall()
    traded = conn.execute(
        "SELECT COUNT(*) FROM prices WHERE trade_date = ?", (latest,)).fetchone()[0]
    print(f"\nOn {latest}: {traded} symbols traded, {len(unmatched)} not in the company list")
    for sym, name in unmatched[:15]:
        print(f"  {sym:12} {name}")

    conn.close()


if __name__ == "__main__":
    run()