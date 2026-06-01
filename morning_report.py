"""
Morning report runner — executes at 8:45AM EST via Task Scheduler.
Fetches market data, runs Claude analysis, generates PDF, saves JSON for aftermarket review.
"""

import os
import sys
import json
import logging
from datetime import date
from dotenv import load_dotenv

# Load .env before importing src modules
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'), override=True)

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from data_fetcher import get_market_snapshot
from analyzer import run_morning_analysis
from pdf_generator import build_morning_pdf
from discord_sender import send_morning_report

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)s  %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f'{date.today()}_morning.log')),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


def main():
    today = date.today().strftime('%Y-%m-%d')
    log.info(f'=== Morning Report Starting: {today} ===')

    # 1. Fetch market data
    log.info('Step 1/3 — Fetching market snapshot...')
    try:
        snapshot = get_market_snapshot()
        log.info(f'  Snapshot: {len(snapshot.get("tickers", []))} tickers, '
                 f'F&G: {snapshot["fear_greed"].get("score")} ({snapshot["fear_greed"].get("rating")})')
    except Exception as e:
        log.error(f'Data fetch failed: {e}')
        sys.exit(1)

    # 2. Run Claude analysis
    log.info('Step 2/3 — Running Claude analysis...')
    try:
        analysis = run_morning_analysis(snapshot)
        analysis['date'] = today
        log.info(f'  Bias: {analysis.get("market_bias")} | Trades: {len(analysis.get("trades", []))}')
    except Exception as e:
        log.error(f'Claude analysis failed: {e}')
        sys.exit(1)

    # 3. Generate PDF
    log.info('Step 3/3 — Generating PDF...')
    try:
        pdf_path = build_morning_pdf(analysis, snapshot)
        log.info(f'  PDF saved: {pdf_path}')
    except Exception as e:
        log.error(f'PDF generation failed: {e}')
        sys.exit(1)

    # Save JSON for aftermarket review
    json_path = os.path.join(DATA_DIR, f'{today}_morning_analysis.json')
    with open(json_path, 'w') as f:
        json.dump({'snapshot': snapshot, 'analysis': analysis}, f, indent=2, default=str)
    log.info(f'  Analysis saved: {json_path}')

    # Send to Discord
    log.info('Sending to Discord...')
    sent = send_morning_report(pdf_path, analysis, snapshot)
    if sent:
        log.info('  Discord: sent successfully')
    else:
        log.warning('  Discord: send failed or webhook not configured')

    log.info(f'=== Morning Report Complete: {pdf_path} ===')
    print(f'\nReport saved to: {pdf_path}')


if __name__ == '__main__':
    main()
