import inspect
from nepse_data_api import Nepse

n = Nepse()
for name in sorted(dir(n)):
    if name.startswith("_"):
        continue
    low = name.lower()
    if any(k in low for k in ("index", "sector", "indices", "sub")):
        obj = getattr(n, name)
        try:
            sig = str(inspect.signature(obj))
        except (TypeError, ValueError):
            sig = ""
        doc = (inspect.getdoc(obj) or "").split("\n")[0]
        print(f"{name}{sig}  {doc}")