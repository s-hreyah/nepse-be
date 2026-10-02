import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from nepse_data_api import Nepse
from app.db import get_connection

NEPAL = ZoneInfo("Asia/Kathmandu")

# The NEPSE index plus the three broad indices, then the 13 sector indices.
BROAD = {58: "NEPSE Index", 57: "Sensitive Index", 62: "Float Index", 63: "Sensitive Float Index"}


def init_indices():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS indices (
            index_id INTEGER NOT NULL,
            name TEXT,
            trade_date TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            turnover REAL, volume INTEGER, transactions INTEGER,
            PRIMARY KEY (index_id, trade_date)
        )
    """)
    conn.commit()
    conn.close()


def fetch(n, idx, start, end):
    for _ in range(3):
        try:
            rows = n.get_index_history(index=idx, start_date=start, end_date=end, size=500)
            if rows:
                return rows
        except Exception as e:
            print(f"  index {idx}: {e}")
        time.sleep(5)
    return []


def run(start, end):
    init_indices()
    n = Nepse()
    targets = dict(BROAD)
    for s in n.get_sub_indices():
        targets[s["id"]] = s["index"]

    conn = get_connection()
    for idx, name in targets.items():
        rows = fetch(n, idx, start, end)
        saved = 0
        for r in rows:
            if not r.get("closingIndex"):      # never save a live or partial row
                continue
            conn.execute(
                """INSERT OR REPLACE INTO indices
                   (index_id, name, trade_date, open, high, low, close,
                    turnover, volume, transactions)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (idx, name, r["businessDate"], r.get("openIndex"), r.get("highIndex"),
                 r.get("lowIndex"), r["closingIndex"], r.get("turnoverValue"),
                 r.get("turnoverVolume"), r.get("totalTransaction")),
            )
            saved += 1
        conn.commit()
        print(f"{idx:>3} {name}: {saved} rows")
        time.sleep(1)
    conn.close()


if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else "2025-10-01"
    end = sys.argv[2] if len(sys.argv) > 2 else datetime.now(NEPAL).date().isoformat()
    run(start, end)