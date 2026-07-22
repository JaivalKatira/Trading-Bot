"""
scan_daily.py
-------------
Runs after market close (~4:00 PM IST). For every symbol in data/EQUITY_L.csv,
pulls daily OHLC data via yfinance, computes RSI(10) with Wilder smoothing and
SMA(200), and flags "candidate" LONG/SHORT calls:

  Candidate LONG  : RSI10 < 30  and close > SMA200
  Candidate SHORT : RSI10 > 70  and close < SMA200

Candidates (plus the day's 0.25/0.75 candle levels) are written to signals.csv
in the repo root. The next morning, validate_gap.py checks whether the actual
opening price confirms the gap-reversion condition before sending any email.
"""

import os
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

REQUEST_PAUSE_SECONDS = 0.3
RSI_PERIOD = 10
SMA_PERIOD = 200

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(REPO_ROOT, "data")
UNIVERSE_FILE = os.path.join(DATA_DIR, "EQUITY_L.csv")
OUTPUT_FILE = os.path.join(REPO_ROOT, "signals.csv")


def load_universe():
    df = pd.read_csv(UNIVERSE_FILE)
    return df["SYMBOL"].astype(str).str.strip().tolist()


def compute_indicators(df):
    df["SMA200"] = df["close"].rolling(window=SMA_PERIOD).mean()

    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / RSI_PERIOD, min_periods=RSI_PERIOD, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / RSI_PERIOD, min_periods=RSI_PERIOD, adjust=False).mean()
    rs = avg_gain / avg_loss
    df["RSI10"] = 100 - (100 / (1 + rs))

    candle_range = df["close"] - df["open"]
    df["Level_025"] = df["open"] + 0.25 * candle_range
    df["Level_075"] = df["open"] + 0.75 * candle_range
    return df


def get_candidate_call(row):
    rsi = row["RSI10"]
    close = row["close"]
    sma200 = row["SMA200"]
    if pd.isna(rsi) or pd.isna(sma200):
        return None
    if rsi < 30 and close > sma200:
        return "LONG"
    if rsi > 70 and close < sma200:
        return "SHORT"
    return None


def main():
    today = datetime.now()
    start_date = today - timedelta(days=400)
    end_date = today + timedelta(days=1)

    symbols = load_universe()
    results = []

    for symbol in symbols:
        try:
            yf_symbol = symbol if symbol.endswith((".NS", ".BO")) else f"{symbol}.NS"
            df = yf.Ticker(yf_symbol).history(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval="1d",
                auto_adjust=False,
            )
            if df is None or df.empty:
                continue

            df = df.reset_index().rename(columns={
                "Date": "datetime", "Open": "open", "High": "high",
                "Low": "low", "Close": "close", "Volume": "volume",
            })
            df["datetime"] = pd.to_datetime(df["datetime"]).dt.tz_localize(None)
            df = df.sort_values("datetime").reset_index(drop=True)
            df = compute_indicators(df)

            last_row = df.iloc[-1]
            call = get_candidate_call(last_row)
            if call:
                results.append({
                    "symbol": symbol,
                    "call": call,
                    "signal_date": last_row["datetime"].strftime("%Y-%m-%d"),
                    "close": round(float(last_row["close"]), 2),
                    "rsi10": round(float(last_row["RSI10"]), 2),
                    "sma200": round(float(last_row["SMA200"]), 2),
                    "level_025": round(float(last_row["Level_025"]), 2),
                    "level_075": round(float(last_row["Level_075"]), 2),
                })
        except Exception as e:
            print(f"Skipping {symbol}: {e}")
        finally:
            time.sleep(REQUEST_PAUSE_SECONDS)

    out_df = pd.DataFrame(results, columns=[
        "symbol", "call", "signal_date", "close", "rsi10",
        "sma200", "level_025", "level_075",
    ])
    out_df.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved {len(out_df)} candidate calls to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
