from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.db import get_connection

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