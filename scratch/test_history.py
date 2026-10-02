import inspect
from nepse_data_api import Nepse

nepse = Nepse()

for name in ("get_historical_chart", "get_price_volume", "get_today_price", "get_index_history"):
    fn = getattr(nepse, name)
    print(f"--- {name}{inspect.signature(fn)}")
    print((inspect.getdoc(fn) or "no docstring")[:400])
    print()