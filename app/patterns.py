import numpy as np
import pandas as pd

# Plain-language rules, kept next to the code so the lesson cards can reuse them.
RULES = {
    "doji": "Body is 10% or less of the day's range: buyers and sellers ended level.",
    "hammer": "Long lower wick (2x the body or more), tiny upper wick, after a 5-day fall.",
    "shooting_star": "Long upper wick (2x the body or more), tiny lower wick, after a 5-day rise.",
    "bull_marubozu": "Green candle whose body is 90% or more of the range: no wicks.",
    "bear_marubozu": "Red candle whose body is 90% or more of the range: no wicks.",
    "bull_engulfing": "Green candle whose body covers the previous red candle's body.",
    "bear_engulfing": "Red candle whose body covers the previous green candle's body.",
    "morning_star": "Long red, then a small body, then a green close above the first candle's midpoint.",
    "evening_star": "Long green, then a small body, then a red close below the first candle's midpoint.",
}


def detect(df):
    """df: one stock, sorted by date, with adj_open/adj_high/adj_low/adj_close.
    Returns a True/False table with one column per pattern."""
    o, h, l, c = df["adj_open"], df["adj_high"], df["adj_low"], df["adj_close"]
    rng = (h - l).where(h > l)
    body = (c - o).abs()
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - l
    green, red = c > o, c < o
    fell, rose = c < c.shift(5), c > c.shift(5)
    big = body > 0.1 * rng

    out = pd.DataFrame(index=df.index)
    out["doji"] = body <= 0.1 * rng
    out["hammer"] = big & (lower >= 2 * body) & (upper <= 0.1 * rng) & fell
    out["shooting_star"] = big & (upper >= 2 * body) & (lower <= 0.1 * rng) & rose
    out["bull_marubozu"] = green & (body >= 0.9 * rng)
    out["bear_marubozu"] = red & (body >= 0.9 * rng)
    out["bull_engulfing"] = red.shift(1) & green & (o <= c.shift(1)) & (c >= o.shift(1))
    out["bear_engulfing"] = green.shift(1) & red & (o >= c.shift(1)) & (c <= o.shift(1))

    small1 = body.shift(1) <= 0.3 * rng.shift(1)
    mid = (o.shift(2) + c.shift(2)) / 2
    out["morning_star"] = (red.shift(2) & (body.shift(2) >= 0.6 * rng.shift(2))
                           & small1 & green & (c > mid))
    out["evening_star"] = (green.shift(2) & (body.shift(2) >= 0.6 * rng.shift(2))
                           & small1 & red & (c < mid))
    return out.fillna(False).astype(bool)