from nepse_data_api import Nepse

n = Nepse()

print("INDEX_MAP:")
print(n.INDEX_MAP)

print("\nget_sub_indices (first 3):")
subs = n.get_sub_indices()
print(type(subs), len(subs))
for s in list(subs)[:3]:
    print(s)

print("\nget_index_history (default index):")
hist = n.get_index_history()
print(type(hist), len(hist))
for row in list(hist)[:3]:
    print(row)
print("...")
for row in list(hist)[-3:]:
    print(row)