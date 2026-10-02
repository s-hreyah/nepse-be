from nepse_data_api import Nepse

nepse = Nepse()
names = [n for n in dir(nepse) if not n.startswith("_")]
print("Candidate methods:")
for n in names:
    if any(k in n.lower() for k in ("compan", "sector", "security", "list", "symbol", "index")):
        print("  ", n)