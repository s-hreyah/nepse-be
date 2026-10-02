from app.db import get_connection

SETUP = ("30 most liquid stocks, walk-forward testing (each prediction uses only earlier days), "
         "test period about April to September 2026, prices adjusted for bonus shares.")

RESULTS = [
    ("Size of tomorrow's move", "20-day average band",
     "An 80% band held 77.6% of real moves on the half of the data it was not fitted on.",
     "Target 80%", "Usable as a rough guide. This is the band on the stock page."),
    ("Size of tomorrow's move", "Smoothed average (EWMA)",
     "Error 1.3% lower than the 20-day average and better in 4 of 5 time blocks, but its band held only 73.8%.",
     "20-day average", "A negligible edge, so it is not used."),
    ("Size of tomorrow's move", "Linear model",
     "Error 3.0% higher than the 20-day average, and better on only 10 of 30 stocks.",
     "20-day average", "No skill."),
    ("Direction of tomorrow's move", "ARIMA(1,0,1)",
     "Right 47.5% of the time. Error 3.2% worse than 'no change', better on only 6 of 30 stocks.",
     "Always guessing down: 57.8%", "No skill. The order was not tuned."),
    ("Direction of tomorrow's move", "Gradient boosting",
     "Right 54.2% of the time. Error 2.1% worse than 'no change'.",
     "Always guessing down: 58.1%", "No skill. Figures from my earlier notes."),
    ("Direction of tomorrow's move", "Candlestick patterns",
     "An apparent effect disappeared when patterns were counted per stock instead of per day.",
     "Base rate of up and down days", "No evidence of skill. Figures from my earlier notes."),
]


def run():
    conn = get_connection()
    conn.execute("DROP TABLE IF EXISTS forecast_results")
    conn.execute("""CREATE TABLE forecast_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT, method TEXT, result TEXT, benchmark TEXT, verdict TEXT)""")
    conn.executemany(
        "INSERT INTO forecast_results (question, method, result, benchmark, verdict) "
        "VALUES (?, ?, ?, ?, ?)", RESULTS)
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('forecast_setup', ?)", (SETUP,))
    conn.commit()
    conn.close()
    print(f"Saved {len(RESULTS)} results")


if __name__ == "__main__":
    run()