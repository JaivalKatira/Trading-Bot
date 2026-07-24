"""
validate_gap.py
----------------
Runs the next trading morning at ~9:20 AM IST (after the market's opening
prints are in). Reads signals.csv (produced by scan_daily.py the previous
afternoon) and checks whether today's actual open confirms the gap-reversion
condition:

  Confirmed LONG  : candidate was LONG  and today's open < Level_025
  Confirmed SHORT : candidate was SHORT and today's open > Level_075

Only confirmed calls are emailed - candidates that don't confirm are dropped
silently, same as the original notebook logic.

FIX (2026-07-24): validate_gap previously ignored the signal_date column
entirely and confirmed whatever rows happened to be in signals.csv. If the
hand-off between the two jobs ever picked up a stale file (failed run,
retried job, caching quirk), this would silently confirm old candidates
against today's open — producing calls that don't correspond to yesterday's
actual scan. We now check signal_date against today's date and skip/report
anything too old.
"""

import os
import time
from datetime import datetime

import pandas as pd
import yfinance as yf

from email_utils import send_email

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
SIGNALS_FILE = os.path.join(REPO_ROOT, "signals.csv")
REQUEST_PAUSE_SECONDS = 0.3
MAX_SIGNAL_STALENESS_DAYS = 3  # generous buffer for weekends/holidays


def get_today_open(symbol):
    yf_symbol = symbol if symbol.endswith((".NS", ".BO")) else f"{symbol}.NS"
    df = yf.Ticker(yf_symbol).history(period="2d", interval="1d", auto_adjust=False)
    if df is None or df.empty:
        return None

    df = df.reset_index()
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.date
    today = datetime.now().date()
    row = df[df["Date"] == today]
    if row.empty:
        return None
    return float(row.iloc[0]["Open"])


def main():
    if not os.path.exists(SIGNALS_FILE):
        print("No signals.csv found (artifact download may have failed) — nothing to validate.")
        return

    signals_df = pd.read_csv(SIGNALS_FILE)
    if signals_df.empty:
        print("signals.csv is empty — no candidates from yesterday's scan.")
        return

    today = datetime.now().date()
    confirmed = []
    skipped_stale = 0

    for _, row in signals_df.iterrows():
        symbol = row["symbol"]
        call = row["call"]
        level_025 = row["level_025"]
        level_075 = row["level_075"]

        # FIX: verify this candidate is actually from a recent scan before
        # trusting it. Without this, a stale signals.csv (e.g. from a failed
        # scan_daily run or a bad hand-off) gets silently confirmed against
        # today's open, producing calls that don't belong to today.
        try:
            signal_date = pd.to_datetime(row["signal_date"]).date()
        except Exception:
            print(f"Skipping {symbol}: unparseable signal_date {row.get('signal_date')!r}")
            continue

        staleness = (today - signal_date).days
        if staleness < 0 or staleness > MAX_SIGNAL_STALENESS_DAYS:
            skipped_stale += 1
            continue

        try:
            today_open = get_today_open(symbol)
            if today_open is None:
                continue
            if call == "LONG" and today_open < level_025:
                confirmed.append(f"{symbol} : LONG CALL (open {today_open:.2f} < {level_025:.2f})")
            elif call == "SHORT" and today_open > level_075:
                confirmed.append(f"{symbol} : SHORT CALL (open {today_open:.2f} > {level_075:.2f})")
        except Exception as e:
            print(f"Skipping {symbol}: {e}")
        finally:
            time.sleep(REQUEST_PAUSE_SECONDS)

    if skipped_stale:
        print(f"Skipped {skipped_stale} candidates with stale signal_date "
              f"(likely a stale/failed previous scan_daily run).")

    if confirmed:
        body = "\n".join(confirmed)
    else:
        body = "No confirmed LONG/SHORT calls today."

    subject = f"NSE Gap Signals - {datetime.now().strftime('%d-%m-%Y')}"

    try:
        send_email(subject, body)
        print("Email sent.")
    except KeyError as e:
        print(f"Email not sent — missing env var: {e}. Set EMAIL_ADDRESS / EMAIL_APP_PASSWORD secrets.")

    print(body)


if __name__ == "__main__":
    main()
