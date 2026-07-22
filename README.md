# NSE Gap Signals

Fully automated, free-to-run daily signal scanner for NSE stocks:

1. **`scan_daily.py`** runs at **4:00 PM IST** (right after market close). It computes RSI(10) with Wilder smoothing and SMA(200) for every symbol in `data/EQUITY_L.csv`, and flags "candidate" calls:
   - **Candidate LONG**: RSI10 < 30 and close > SMA200
   - **Candidate SHORT**: RSI10 > 70 and close < SMA200

   Results (with that day's 0.25/0.75 candle levels) are saved to `signals.csv` and uploaded as a GitHub Actions artifact.

2. **`validate_gap.py`** runs the next morning at **9:20 AM IST**. It downloads yesterday's `signals.csv` artifact and checks whether the actual opening price confirms the gap-reversion condition:
   - **Confirmed LONG**: candidate was LONG and today's open < Level_025
   - **Confirmed SHORT**: candidate was SHORT and today's open > Level_075

   Only confirmed calls are emailed to you. Everything else is silently dropped.

Both jobs run for free on **GitHub Actions** — no server to rent or maintain.

> This is a technical-analysis scanner, not financial advice. Do your own research before acting on any signal.

## Setup (5 minutes)

### 1. Fork or clone this repo

### 2. Replace the stock universe
`data/EQUITY_L.csv` ships with a 5-stock sample so you can test end-to-end quickly. For the full NSE universe, download the official list from [nseindia.com](https://www.nseindia.com/market-data/securities-available-for-trading) (the "Equity List" CSV) and replace `data/EQUITY_L.csv` — it just needs a `SYMBOL` column.

### 3. Create a Gmail App Password
Regular Gmail passwords won't work with SMTP. Generate a dedicated one:
1. Turn on 2-Step Verification on your Google Account (if not already on).
2. Go to **Google Account → Security → App Passwords**.
3. Create a new app password (name it anything, e.g. "NSE Gap Signals").
4. Copy the 16-character password — you'll only see it once.

### 4. Add GitHub Secrets
In your forked repo: **Settings → Secrets and variables → Actions → New repository secret**. Add:

| Secret name | Value |
|---|---|
| `EMAIL_ADDRESS` | Your Gmail address (the one sending mail) |
| `EMAIL_APP_PASSWORD` | The 16-character App Password from step 3 |
| `EMAIL_TO` | *(optional)* Where to send it — defaults to `EMAIL_ADDRESS`, i.e. you email yourself |

### 5. Enable Actions
Go to the **Actions** tab of your repo and enable workflows if prompted. The two scheduled workflows (`scan.yml`, `validate.yml`) will now run automatically on weekdays.

### 6. Test it manually
Both workflows have a `workflow_dispatch` trigger, so you can run them on demand from the **Actions** tab without waiting for the schedule — useful for a first test end-to-end.

## Project structure

```
.
├── data/
│   └── EQUITY_L.csv          # stock universe (SYMBOL column)
├── scripts/
│   ├── scan_daily.py         # day 0: generates candidate calls
│   ├── validate_gap.py       # day 1: confirms + emails calls
│   └── email_utils.py        # shared SMTP sender
├── .github/workflows/
│   ├── scan.yml               # cron: 4:00 PM IST, Mon-Fri
│   └── validate.yml           # cron: 9:20 AM IST, Mon-Fri
├── requirements.txt
└── signals.csv                # generated daily, not committed (see .gitignore)
```

## Notes on the artifact-based state

`signals.csv` is never committed to the repo. It's uploaded as a **GitHub Actions artifact** by `scan.yml` and pulled back down the next morning by `validate.yml` (via [`dawidd6/action-download-artifact`](https://github.com/dawidd6/action-download-artifact), which can fetch an artifact from a different workflow's most recent successful run). Artifacts expire after 3 days, so if a scheduled run is skipped or fails, the next validate run will just find nothing to check and exit quietly.

## Local testing

```bash
pip install -r requirements.txt

# Day 0
python scripts/scan_daily.py

# Day 1 (set env vars first, or skip email and just inspect signals.csv/output)
export EMAIL_ADDRESS="you@gmail.com"
export EMAIL_APP_PASSWORD="xxxxxxxxxxxxxxxx"
python scripts/validate_gap.py
```

## Customizing the schedule

Both cron times are in UTC inside the workflow YAML files (GitHub Actions doesn't support IST directly):

- `30 10 * * 1-5` → 4:00 PM IST
- `50 3 * * 1-5` → 9:20 AM IST

Adjust if you want different timing, and note GitHub's scheduled workflows can be delayed by a few minutes during high load — don't rely on them for split-second timing.
