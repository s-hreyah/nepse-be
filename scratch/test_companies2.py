import inspect
from nepse_data_api import Nepse

nepse = Nepse()

names = ["get_company_list", "get_security_list", "get_sector_list",
         "get_holiday_list", "get_security_details", "get_company_news"]

for n in names:
    fn = getattr(nepse, n)
    print(f"--- {n}{inspect.signature(fn)}")
    print((inspect.getdoc(fn) or "no docstring")[:250])
    print()

# Safe sample calls (no arguments needed)
for n in ["get_company_list", "get_security_list", "get_sector_list", "get_holiday_list"]:
    try:
        data = getattr(nepse, n)()
        size = len(data) if data else 0
        print(f"=== {n}: {size} items")
        if data:
            first = data[0] if isinstance(data, list) else data
            print("First:", first)
    except Exception as ex:
        print(f"=== {n}: error {ex}")
    print()