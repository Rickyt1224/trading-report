# Daily Trading Report System

An automated pre-market and post-market trading report generator focused on QQQ, tech, and broad market movers. Runs daily on Windows via Task Scheduler, generates PDF reports powered by the Claude AI API.

---

## What It Does

### Morning Report (8:45 AM EST — weekdays)
- Scans 40+ tickers across QQQ holdings, tech sector, and broad market movers
- Filters out penny stocks (price < $5, volume < 500k)
- Pulls macro context: Fear & Greed Index, Treasury yields (2Y / 10Y / 30Y), economic calendar events, and top market headlines
- Cross-references each stock price across 3 sources (Yahoo Finance, Finviz, WSJ)
- Checks premarket price and gap % for each pick
- Flags unusual options flow (call/put volume vs open interest)
- Sends all data to Claude AI which selects the **Top 10 trades** with:
  - If/Then entry triggers
  - Secondary triggers
  - Avoid conditions
  - Support / resistance levels
  - Analyst price targets
  - Conviction rating (High / Medium / Low)
- Generates a 1-page PDF report
- Saves analysis JSON for aftermarket review

### Aftermarket Report (4:45 PM EST — weekdays)
- Loads today's morning picks
- Fetches end-of-day OHLCV data for each ticker
- Flags any picks with earnings within 5 days (color-coded by urgency)
- Claude reviews each trade: what triggered, what didn't, outcome
- Generates improvement suggestions (rule changes) for your review
- **No rule changes are made without your explicit approval**

---

## Report Layout

### Page 1 — Morning Snapshot
| Section | Contents |
|---|---|
| Title bar | Date, report type |
| Macro panel | Fear & Greed gauge · Market bias · Yields (2Y/10Y/30Y) with trend arrows · Key economic event · Headlines |
| Trade table | Rank · Ticker · Direction · Close · Pre-market $ · Gap % · Chg % · Vol/Avg · Support · Resistance · Analyst target · Conviction · If/Then setup + Catalyst + Options flow + Price sources |

### Aftermarket Report
| Section | Contents |
|---|---|
| Summary | Accuracy score, overall assessment |
| Trade review table | Each pick: open/high/low/close, outcome, triggered?, what worked, what failed, lesson |
| Earnings calendar | Upcoming earnings for today's picks (5-day window) |
| Improvement suggestions | Proposed rule changes — **pending your approval** |

---

## Project Structure

```
G:\Trading Report\
│
├── morning_report.py          # Main morning runner (called by Task Scheduler)
├── aftermarket_report.py      # Aftermarket runner
├── preview_charts.py          # Chart layout preview tool (dev use)
├── run_morning.bat            # Batch file for Task Scheduler
├── run_aftermarket.bat        # Batch file for Task Scheduler
├── requirements.txt           # Python dependencies
├── .env                       # API keys (never committed)
│
├── src/
│   ├── data_fetcher.py        # All data sources: F&G, yields, Finviz, yfinance, options, earnings, news
│   ├── analyzer.py            # Claude API prompts and response parsing
│   └── pdf_generator.py       # ReportLab PDF layout for both reports
│
├── reports/                   # Generated PDFs (YYYY-MM-DD_morning.pdf, etc.)
├── data/                      # Saved JSON analysis files + chart images cache
│   ├── charts/                # Cached chart PNGs
│   └── YYYY-MM-DD_morning_analysis.json
└── logs/                      # Daily run logs
```

---

## Setup

### Requirements
- Windows 10/11
- Python 3.12+
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com))

### Install
```bash
pip install -r requirements.txt
```

### Configure `.env`
```
ANTHROPIC_API_KEY=sk-ant-...
EMAIL_ADDRESS=your@email.com
EMAIL_RECIPIENT=your@email.com
GMAIL_APP_PASSWORD=           # leave blank until email is enabled
```

### Task Scheduler
Two tasks are pre-registered automatically:

| Task Name | Schedule | Script |
|---|---|---|
| `TradingReport_Morning` | 8:45 AM Mon–Fri | `run_morning.bat` |
| `TradingReport_Aftermarket` | 4:45 PM Mon–Fri | `run_aftermarket.bat` |

To verify: open **Task Scheduler** → look for `TradingReport_Morning` and `TradingReport_Aftermarket`.

### Run Manually
```bash
py morning_report.py
py aftermarket_report.py
```

---

## Data Sources (all free)

| Source | Used For |
|---|---|
| Yahoo Finance (yfinance) | Price, volume, technicals, premarket, earnings dates |
| Finviz | Top gainers/losers screener, price cross-reference |
| WSJ | Price cross-reference (3rd source) |
| CNN (scrape) | Fear & Greed Index |
| FRED / Treasury | Treasury yields (2Y, 10Y, 30Y) |
| Finnhub (free tier) | News headlines |
| Yahoo Finance RSS | Broad market headlines |

---

## Cost Estimate

| Item | Monthly |
|---|---|
| Claude API (Sonnet 4.6) | ~$5–10 |
| All data sources | Free |
| **Total** | **~$5–10/month** |

Based on ~21 trading days × 2 reports/day × ~$0.20/report.

---

## Improvement Workflow

After each aftermarket report, Claude suggests rule changes based on what worked and what didn't. **No changes are applied automatically.** The workflow is:

1. Review the aftermarket PDF's *Suggested Rule Improvements* section
2. Reply **APPROVE** or **DENY** for each suggestion in the next session
3. Approved changes are applied manually with your confirmation

---

## Report Versioning

Reports auto-increment if a file already exists for the day:
- `2026-05-31_morning.pdf` → `2026-05-31_morning_rev02.pdf` → `rev03` etc.
- Old versions are never overwritten

---

## Roadmap / Pending
- [ ] Email delivery (GMAIL_APP_PASSWORD not yet configured)
- [ ] Company logos under ticker names
- [ ] Polygon.io integration for real-time premarket data
