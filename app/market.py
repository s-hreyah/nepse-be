from datetime import date

# Before this date: Sunday to Thursday. From this date: Monday to Friday.
CHANGE_DATE = date(2026, 4, 6)


def is_trading_weekday(d):
    if d >= CHANGE_DATE:
        return d.weekday() <= 4              # Mon=0 ... Fri=4
    return d.weekday() in (6, 0, 1, 2, 3)    # Sun, Mon, Tue, Wed, Thu