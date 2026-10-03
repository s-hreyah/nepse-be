import sys
import glob
import os
import pandas as pd

target = sys.argv[1]
files = sorted(glob.glob(os.path.join(target, "**", "*.csv"), recursive=True)) if os.path.isdir(target) else [target]
print(f"{len(files)} csv file(s)")
for f in files[:5]:
    print("  ", f, f"{os.path.getsize(f) / 1e6:.2f} MB")

df = pd.read_csv(files[0])
print("\nFirst file:", files[0])
print("rows:", len(df))
print("columns:", list(df.columns))
print("\nhead:")
print(df.head(5).to_string())
print("\ntail:")
print(df.tail(5).to_string())

for c in df.columns:
    if "date" in c.lower():
        d = pd.to_datetime(df[c], errors="coerce")
        print(f"\ndate column '{c}': {d.min().date()} to {d.max().date()}, {d.isna().sum()} unreadable")
        print("trading days per year:")
        print(d.dt.year.value_counts().sort_index().to_string())
        break

num = df.select_dtypes("number")
print("\nzero or negative values per numeric column:")
print((num <= 0).sum().to_string())
print("\nmissing values per column:")
print(df.isna().sum().to_string())