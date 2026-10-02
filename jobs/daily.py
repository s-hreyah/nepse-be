from datetime import datetime, timedelta

from jobs.ingest_prices import run as ingest
from jobs.ingest_indices import run as ingest_indices, NEPAL
from jobs.build_adjusted import run as adjust
from jobs.checks import run as check

print("=== 1. Ingest prices ===")
ingest()

print("\n=== 2. Ingest indices (last 7 days) ===")
today = datetime.now(NEPAL).date()
ingest_indices((today - timedelta(days=7)).isoformat(), today.isoformat())

print("\n=== 3. Adjusted close ===")
adjust()

print("\n=== 4. Data checks ===")
check()