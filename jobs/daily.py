from jobs.ingest_prices import run as ingest
from jobs.build_adjusted import run as adjust
from jobs.checks import run as check

print("=== 1. Ingest prices ===")
ingest()
print("\n=== 2. Adjusted close ===")
adjust()
print("\n=== 3. Data checks ===")
check()