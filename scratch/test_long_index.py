from nepse_data_api import Nepse

n = Nepse()
tests = [
    ("control: recent month",      "2026-09-01", "2026-09-30"),
    ("edge: first month we have",  "2025-10-01", "2025-10-31"),
    ("just before our data",       "2025-09-01", "2025-09-30"),
    ("one year earlier",           "2024-10-01", "2025-09-30"),
    ("one month, two years ago",   "2024-09-01", "2024-09-30"),
    ("one month, five years ago",  "2021-09-01", "2021-09-30"),
]
for label, start, end in tests:
    try:
        rows = n.get_index_history(index=58, start_date=start, end_date=end, size=500)
        ds = sorted(r["businessDate"] for r in rows)
        print(f"{label:28} {start} to {end}: {len(rows):>3} rows", (ds[0], ds[-1]) if ds else "")
    except Exception as e:
        print(f"{label:28} {start} to {end}: error {e}")