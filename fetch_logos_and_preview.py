import json, sys
sys.path.insert(0, 'src')
from dotenv import load_dotenv
load_dotenv('.env', override=True)

import yfinance as yf
from data_fetcher import download_logo
from pdf_generator import build_morning_pdf

with open('data/2026-05-31_morning_analysis.json') as f:
    data = json.load(f)

# Fetch website and cache logos for every ticker in the snapshot
for t in data['snapshot']['tickers']:
    if not t.get('website'):
        try:
            t['website'] = yf.Ticker(t['ticker']).info.get('website', '')
        except Exception:
            t['website'] = ''
    if t.get('website'):
        p = download_logo(t['ticker'], t['website'])
        if p:
            t['logo_path'] = p
            print(f'  Logo: {t["ticker"]}')

path = build_morning_pdf(
    data['analysis'],
    data['snapshot'],
    output_path='reports/2026-05-31_morning_rev07.pdf'
)
print('Saved:', path)
