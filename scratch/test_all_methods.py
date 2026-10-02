# scratch/test_all_methods.py
import inspect
from nepse_data_api import Nepse

n = Nepse()
for name in sorted(dir(n)):
    if name.startswith("_"):
        continue
    obj = getattr(n, name)
    if not callable(obj):
        continue
    try:
        sig = str(inspect.signature(obj))
    except (TypeError, ValueError):
        sig = ""
    doc = (inspect.getdoc(obj) or "").split("\n")[0]
    print(f"{name}{sig}  {doc}")