from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from app.patterns import detect, RULES
from app.lessons import LESSONS
from app.db import get_connection
import pandas as pd

app = FastAPI(title="NEPSE Monitor API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def rows(sql, params=()):
    conn = get_connection()
    conn.row_factory = lambda cur, r: {c[0]: v for c, v in zip(cur.description, r)}
    data = conn.execute(sql, params).fetchall()
    conn.close()
    return data


def latest_date():
    return rows("SELECT MAX(trade_date) AS d FROM prices")[0]["d"]


@app.get("/health")
def health():
    return {"ok": True, "latest_date": latest_date()}


@app.get("/market/summary")
def market_summary():
    d = latest_date()
    base = ("SELECT p.symbol, p.name, c.sector, p.close, p.prev_close, p.pct_change, "
            "p.volume, p.turnover FROM prices p "
            "JOIN companies c ON c.symbol = p.symbol "
            "WHERE p.trade_date = ? AND c.instrument_type = 'Equity' AND p.volume > 0 ")
    return {
        "date": d,
        "stocks_traded": rows(
            "SELECT COUNT(*) AS n FROM prices p JOIN companies c ON c.symbol = p.symbol "
            "WHERE p.trade_date = ? AND c.instrument_type = 'Equity' AND p.volume > 0",
            (d,))[0]["n"],
        "gainers": rows(base + "ORDER BY p.pct_change DESC LIMIT 10", (d,)),
        "losers": rows(base + "ORDER BY p.pct_change ASC LIMIT 10", (d,)),
        "most_traded": rows(base + "ORDER BY p.turnover DESC LIMIT 10", (d,)),
    }


@app.get("/stocks")
def stocks(q: str = "", date: str = "", sector: str = "", kind: str = "Equity",
           limit: int = Query(100, le=500)):
    d = date or latest_date()
    sql = ("SELECT p.symbol, p.name, c.sector, c.instrument_type, p.open, p.high, p.low, "
           "p.close, p.prev_close, p.pct_change, p.volume, p.turnover "
           "FROM prices p LEFT JOIN companies c ON c.symbol = p.symbol "
           "WHERE p.trade_date = ? ")
    params = [d]
    if kind != "all":
        sql += "AND c.instrument_type = ? "
        params.append(kind)
    if sector:
        sql += "AND c.sector = ? "
        params.append(sector)
    if q:
        sql += "AND (p.symbol LIKE ? OR p.name LIKE ?) "
        params += [f"%{q}%", f"%{q}%"]
    sql += "ORDER BY p.turnover DESC LIMIT ?"
    params.append(limit)
    return {"date": d, "stocks": rows(sql, tuple(params))}


@app.get("/sectors")
def sectors():
    return rows("SELECT sector, COUNT(*) AS companies FROM companies "
                "WHERE instrument_type = 'Equity' GROUP BY sector ORDER BY companies DESC")

@app.get("/stocks/{symbol}/history")
def stock_history(symbol: str, days: int = Query(250, le=400)):
    symbol = symbol.upper()
    data = rows(
        "SELECT trade_date, open, high, low, close, adj_close, volume, turnover "
        "FROM prices WHERE symbol = ? ORDER BY trade_date", (symbol,))
    if not data:
        raise HTTPException(404, f"No price history for {symbol}")

    df = pd.DataFrame(data)
    # averages are computed on the full history, then we cut to the last N days
    df["ma20"] = df["adj_close"].rolling(20).mean()
    df["ma50"] = df["adj_close"].rolling(50).mean()
    df["return_pct"] = df["adj_close"].pct_change() * 100
    factor = df["adj_close"] / df["close"].where(df["close"] > 0)
    for col in ("open", "high", "low"):
        df[f"adj_{col}"] = df[col] * factor
    df = df.tail(days).round(2).astype(object)
    df = df.where(df.notna(), None)

    info = rows("SELECT name, sector, instrument_type FROM companies WHERE symbol = ?", (symbol,))
    return {
        "symbol": symbol,
        "company": info[0] if info else None,
        "points": df.to_dict("records"),
    }

BROAD_IDS = {57, 58, 62, 63}


@app.get("/indices")
def indices():
    data = rows(
        "SELECT index_id, name, trade_date, close, prev_close, "
        "ROUND((close - prev_close) / prev_close * 100, 2) AS pct_change FROM ("
        "  SELECT index_id, name, trade_date, close, "
        "  LAG(close) OVER (PARTITION BY index_id ORDER BY trade_date) AS prev_close "
        "  FROM indices) "
        "WHERE trade_date = (SELECT MAX(trade_date) FROM indices) "
        "ORDER BY index_id")
    for r in data:
        r["group"] = "broad" if r["index_id"] in BROAD_IDS else "sector"
    return {"date": data[0]["trade_date"] if data else None, "indices": data}


@app.get("/indices/{index_id}/history")
def index_history(index_id: int, days: int = Query(250, le=400)):
    data = rows(
        "SELECT trade_date, open, high, low, close, turnover, volume "
        "FROM indices WHERE index_id = ? ORDER BY trade_date", (index_id,))
    if not data:
        raise HTTPException(404, f"No history for index {index_id}")
    name = rows("SELECT name FROM indices WHERE index_id = ? LIMIT 1", (index_id,))[0]["name"]

    df = pd.DataFrame(data)
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma50"] = df["close"].rolling(50).mean()
    df["return_pct"] = df["close"].pct_change() * 100
    df = df.tail(days).round(2).astype(object)
    df = df.where(df.notna(), None)
    return {"index_id": index_id, "name": name, "points": df.to_dict("records")}

def init_watchlist():
    conn = get_connection()
    conn.execute("CREATE TABLE IF NOT EXISTS watchlist "
                 "(symbol TEXT PRIMARY KEY, added_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()


init_watchlist()


@app.get("/watchlist")
def watchlist():
    d = latest_date()
    items = rows(
        "SELECT w.symbol, p.name, c.sector, p.close, p.pct_change, p.volume, p.turnover "
        "FROM watchlist w "
        "LEFT JOIN prices p ON p.symbol = w.symbol AND p.trade_date = ? "
        "LEFT JOIN companies c ON c.symbol = w.symbol "
        "ORDER BY w.added_at", (d,))
    return {"date": d, "items": items}


@app.post("/watchlist/{symbol}")
def watch_add(symbol: str):
    symbol = symbol.upper()
    if not rows("SELECT 1 AS x FROM companies WHERE symbol = ?", (symbol,)):
        raise HTTPException(404, f"Unknown symbol {symbol}")
    conn = get_connection()
    conn.execute("INSERT OR IGNORE INTO watchlist (symbol) VALUES (?)", (symbol,))
    conn.commit()
    conn.close()
    return {"ok": True, "symbol": symbol}


@app.delete("/watchlist/{symbol}")
def watch_remove(symbol: str):
    conn = get_connection()
    conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol.upper(),))
    conn.commit()
    conn.close()
    return {"ok": True, "symbol": symbol.upper()}

MARKED = ["hammer", "shooting_star", "bull_engulfing", "bear_engulfing",
          "morning_star", "evening_star"]   # doji and marubozu are too common to mark


@app.get("/patterns/lessons")
def pattern_lessons():
    try:
        stats = {r["pattern"]: r for r in rows("SELECT * FROM pattern_stats")}
    except Exception:
        stats = {}
    lessons = [{"key": k, "rule": RULES[k], **LESSONS[k], "stats": stats.get(k)} for k in RULES]
    return {"base": stats.get("all_days"), "lessons": lessons}


@app.get("/stocks/{symbol}/patterns")
def stock_patterns(symbol: str, days: int = Query(250, le=400)):
    symbol = symbol.upper()
    data = rows("SELECT trade_date, open, high, low, close, adj_close, volume "
                "FROM prices WHERE symbol = ? ORDER BY trade_date", (symbol,))
    if not data:
        raise HTTPException(404, f"No price history for {symbol}")
    df = pd.DataFrame(data)
    f = df["adj_close"] / df["close"].where(df["close"] > 0)
    for col in ("open", "high", "low"):
        df[f"adj_{col}"] = df[col] * f
    df = df[df["volume"] > 0].reset_index(drop=True)
    sig = detect(df)
    cutoff = df["trade_date"].iloc[-days:].min()
    found = []
    for i in range(len(df)):
        names = [k for k in MARKED if sig.at[i, k]]
        if names and df.at[i, "trade_date"] >= cutoff:
            found.append({"trade_date": df.at[i, "trade_date"], "patterns": names})
    return {"symbol": symbol, "found": found}

BAND_MULT = 1.5   # fitted on the first half of the walk-forward test; 77.6% coverage on the second half


@app.get("/stocks/{symbol}/forecast")
def stock_forecast(symbol: str):
    symbol = symbol.upper()
    data = rows(
        "SELECT trade_date, close, adj_close FROM prices "
        "WHERE symbol = ? AND adj_close > 0 ORDER BY trade_date", (symbol,))
    if not data:
        raise HTTPException(404, f"No price history for {symbol}")
    if len(data) < 40:
        return {
            "available": False,
            "symbol": symbol,
            "reason": f"Only {len(data)} trading days in the last year, too few for a forecast band.",
        }

    df = pd.DataFrame(data)
    moves = df["adj_close"].pct_change().abs() * 100
    avg20 = float(moves.tail(20).mean())
    band = min(BAND_MULT * avg20, 15.0)          # NEPSE's daily limit is 15%

    span = (pd.to_datetime(df["trade_date"].iloc[-1]) - pd.to_datetime(df["trade_date"].iloc[-21])).days
    last_close = float(df["close"].iloc[-1])
    return {
        "available": True,
        "symbol": symbol,
        "as_of": df["trade_date"].iloc[-1],
        "last_close": round(last_close, 2),
        "avg_abs_move_20d_pct": round(avg20, 2),
        "band_pct": round(band, 2),
        "low": round(last_close * (1 - band / 100), 2),
        "high": round(last_close * (1 + band / 100), 2),
        "thin": span > 45,        # the last 20 trades cover over 6 weeks: thinly traded
        "method": "1.5 x the 20-day average absolute move",
        "tested_coverage_pct": 77.6,
    }

@app.get("/forecast/evidence")
def forecast_evidence():
    try:
        results = rows("SELECT question, method, result, benchmark, verdict FROM forecast_results ORDER BY id")
        setup = rows("SELECT value FROM meta WHERE key = 'forecast_setup'")
    except Exception:
        results, setup = [], []
    return {"setup": setup[0]["value"] if setup else "", "results": results}

RANGE_K = {5: 1.74, 10: 1.75, 20: 1.91}   # fitted on the first half, see jobs/forecast_horizon.py


@app.get("/stocks/{symbol}/range")
def stock_range(symbol: str):
    symbol = symbol.upper()
    data = rows("SELECT trade_date, close, adj_close FROM prices "
                "WHERE symbol = ? AND volume > 0 AND adj_close > 0 ORDER BY trade_date", (symbol,))
    if not data:
        raise HTTPException(404, f"No price history for {symbol}")
    if len(data) < 100:
        return {"symbol": symbol, "available": False,
                "reason": f"Only {len(data)} trading days, too thin for a range."}
    df = pd.DataFrame(data)
    m20 = float((df["adj_close"].pct_change() * 100).abs().tail(20).mean())
    last = float(df["close"].iloc[-1])
    out = []
    for h, k in RANGE_K.items():
        half = k * m20 * (h ** 0.5)
        out.append({"days": h, "plus_minus_pct": round(half, 1),
                    "low": round(last * (1 - half / 100), 2),
                    "high": round(last * (1 + half / 100), 2)})

    ev = rows("SELECT book_close, cash_pct, bonus_pct FROM corporate_actions "
              "WHERE symbol = ? AND book_close > ? AND book_close <= date(?, '+30 days') "
              "AND (COALESCE(cash_pct, 0) > 0 OR COALESCE(bonus_pct, 0) > 0) "
              "ORDER BY book_close LIMIT 1", (symbol, df["trade_date"].iloc[-1], df["trade_date"].iloc[-1]))
    event = None
    if ev:
        b, c = (ev[0]["bonus_pct"] or 0), (ev[0]["cash_pct"] or 0)
        expected = ((last / (1 + b / 100) - c) / last - 1) * 100
        event = {**ev[0], "expected_drop_pct": round(expected, 1)}
    return {"symbol": symbol, "available": True, "last_close": last,
            "as_of": df["trade_date"].iloc[-1], "avg_daily_move_pct": round(m20, 2),
            "ranges": out, "event": event}

@app.get("/events/upcoming")
def upcoming_events(days: int = Query(30, le=120)):
    today = latest_date()
    data = rows(
        "SELECT a.symbol, p.name, c.sector, a.book_close, a.agm_date, a.cash_pct, "
        "a.bonus_pct, a.added_date "
        "FROM corporate_actions a "
        "LEFT JOIN companies c ON c.symbol = a.symbol "
        "LEFT JOIN prices p ON p.symbol = a.symbol AND p.trade_date = ? "
        "WHERE a.book_close >= ? AND a.book_close <= date(?, '+' || ? || ' days') "
        "AND (COALESCE(a.cash_pct, 0) > 0 OR COALESCE(a.bonus_pct, 0) > 0) "
        "ORDER BY a.book_close, a.symbol", (today, today, today, days))
    for r in data:
        b = r["bonus_pct"] or 0
        r["bonus_price_effect_pct"] = round(-b / (100 + b) * 100, 2) if b else 0
    return {"from": today, "days": days, "events": data}