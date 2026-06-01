"""
Aftermarket report runner — executes at 4:45PM EST via Task Scheduler.
Loads today's morning analysis, fetches EOD data, runs review, generates PDF.
"""

import os
import sys
import json
import logging
import yfinance as yf
from datetime import date
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'), override=True)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from analyzer import run_aftermarket_analysis
from pdf_generator import build_aftermarket_pdf
from data_fetcher import get_earnings_dates

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)s  %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f'{date.today()}_aftermarket.log')),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


def fetch_eod_data(tickers: list) -> dict:
    """Fetch end-of-day OHLCV for each ticker."""
    eod = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period='1d')
            if not hist.empty:
                row = hist.iloc[-1]
                eod[ticker] = {
                    'open': round(row['Open'], 2),
                    'high': round(row['High'], 2),
                    'low': round(row['Low'], 2),
                    'close': round(row['Close'], 2),
                    'volume': int(row['Volume']),
                }
        except Exception as e:
            log.warning(f'  EOD fetch failed for {ticker}: {e}')
    return eod


def main():
    today = date.today().strftime('%Y-%m-%d')
    log.info(f'=== Aftermarket Report Starting: {today} ===')

    # Load today's morning analysis
    json_path = os.path.join(DATA_DIR, f'{today}_morning_analysis.json')
    if not os.path.exists(json_path):
        log.error(f'No morning analysis found for {today}: {json_path}')
        sys.exit(1)

    with open(json_path) as f:
        data = json.load(f)

    morning_analysis = data.get('analysis', {})
    trades = morning_analysis.get('trades', [])
    tickers = [t['ticker'] for t in trades]

    log.info(f'  Loaded {len(tickers)} trades from morning report')

    # Fetch EOD data
    log.info('Step 1/3 — Fetching EOD price data...')
    eod_data = fetch_eod_data(tickers)
    log.info(f'  EOD data fetched for {len(eod_data)} tickers')

    # Always include QQQ and SPY as market context
    index_eod = fetch_eod_data(['QQQ', 'SPY'])
    log.info(f'  Index EOD: {list(index_eod.keys())}')

    # Fetch earnings calendar for today's picks
    log.info('Step 2/4 — Fetching earnings calendar...')
    earnings = get_earnings_dates(tickers, days_ahead=5)
    log.info(f'  Earnings flags: {earnings}')

    # Run aftermarket analysis
    log.info('Step 3/4 — Running Claude aftermarket review...')
    try:
        review = run_aftermarket_analysis(morning_analysis, eod_data)
        log.info(f'  Accuracy: {review.get("overall_accuracy")}')
    except Exception as e:
        log.error(f'Claude aftermarket analysis failed: {e}')
        sys.exit(1)

    # Attach earnings and index data to review so PDF can render them
    review['earnings_calendar'] = earnings
    review['index_eod'] = index_eod

    # Generate PDF
    log.info('Step 4/4 — Generating aftermarket PDF...')
    try:
        pdf_path = build_aftermarket_pdf(review, date_str=today)
        log.info(f'  PDF saved: {pdf_path}')
    except Exception as e:
        log.error(f'PDF generation failed: {e}')
        sys.exit(1)

    # Save review JSON for approval tracking
    review_path = os.path.join(DATA_DIR, f'{today}_aftermarket_review.json')
    with open(review_path, 'w') as f:
        json.dump(review, f, indent=2, default=str)
    log.info(f'  Review saved: {review_path}')

    log.info(f'=== Aftermarket Report Complete: {pdf_path} ===')
    print(f'\nReport saved to: {pdf_path}')


if __name__ == '__main__':
    main()
