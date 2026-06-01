"""
Data fetcher: market context, scanner, price cross-reference, technicals.
"""

import os
import re
import json
import time
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, date
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

# ---------------------------------------------------------------------------
# Fear & Greed Index
# ---------------------------------------------------------------------------

def get_fear_greed() -> dict:
    try:
        url = 'https://production.dataviz.cnn.io/index/fearandgreed/graphdata'
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        score = data['fear_and_greed']['score']
        rating = data['fear_and_greed']['rating']
        return {'score': round(score, 1), 'rating': rating.title()}
    except Exception as e:
        return {'score': 'N/A', 'rating': 'Unavailable', 'error': str(e)}


# ---------------------------------------------------------------------------
# Treasury Yields
# ---------------------------------------------------------------------------

def get_treasury_yields() -> dict:
    tickers = {
        '2Y': '^IRX',   # 13-week proxy; use TNX for 10Y
        '10Y': '^TNX',
        '30Y': '^TYX',
    }
    yields = {}
    for label, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period='2d')
            if not hist.empty:
                val = round(hist['Close'].iloc[-1], 3)
                prev = round(hist['Close'].iloc[-2], 3) if len(hist) > 1 else val
                yields[label] = {'value': val, 'change': round(val - prev, 3)}
            else:
                yields[label] = {'value': 'N/A', 'change': 0}
        except Exception as e:
            yields[label] = {'value': 'N/A', 'change': 0, 'error': str(e)}
    return yields


# ---------------------------------------------------------------------------
# Economic Calendar (Yahoo Finance news scrape for macro events)
# ---------------------------------------------------------------------------

def get_economic_events() -> list:
    try:
        url = 'https://finance.yahoo.com/calendar/economic/'
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, 'lxml')
        events = []
        rows = soup.select('table tbody tr')
        for row in rows[:10]:
            cols = row.find_all('td')
            if len(cols) >= 3:
                events.append({
                    'event': cols[0].get_text(strip=True),
                    'time': cols[1].get_text(strip=True),
                    'actual': cols[2].get_text(strip=True) if len(cols) > 2 else '',
                })
        return events[:8]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Finviz premarket movers scanner (no API key needed)
# ---------------------------------------------------------------------------

def get_finviz_movers() -> list:
    """Scan Finviz for top premarket movers: price >$5, volume filter."""
    try:
        url = (
            'https://finviz.com/screener.ashx?v=111&s=ta_topgainers'
            '&f=sh_price_o5,sh_avgvol_o500'
            '&o=-change'
        )
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'lxml')
        tickers = []
        table = soup.find('table', {'id': 'screener-views-table'})
        if not table:
            # fallback: look for ticker links
            links = soup.select('a.screener-link-primary')
            tickers = [a.get_text(strip=True) for a in links[:30]]
        else:
            rows = table.find_all('tr')[1:]
            for row in rows[:30]:
                cols = row.find_all('td')
                if cols:
                    ticker = cols[1].get_text(strip=True) if len(cols) > 1 else ''
                    if ticker:
                        tickers.append(ticker)
        return tickers
    except Exception:
        return []


def get_finviz_losers() -> list:
    try:
        url = (
            'https://finviz.com/screener.ashx?v=111&s=ta_toplosers'
            '&f=sh_price_o5,sh_avgvol_o500'
            '&o=change'
        )
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'lxml')
        links = soup.select('a.screener-link-primary')
        return [a.get_text(strip=True) for a in links[:20]]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Core watchlist (QQQ top holdings + tech ETFs)
# ---------------------------------------------------------------------------

CORE_WATCHLIST = [
    'QQQ', 'TQQQ', 'SQQQ',
    'AAPL', 'MSFT', 'NVDA', 'META', 'AMZN', 'GOOGL', 'TSLA', 'AVGO',
    'AMD', 'SMCI', 'MU', 'INTC', 'QCOM', 'CRM', 'ORCL', 'NFLX',
    'SPY', 'SPXL', 'SPXS', 'XLK', 'SOXX',
]


# ---------------------------------------------------------------------------
# yfinance: price, volume, technicals for a ticker
# ---------------------------------------------------------------------------

def get_ticker_data(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        info = t.info
        hist = t.history(period='35d')

        if hist.empty or len(hist) < 2:
            return {}

        last = hist.iloc[-1]
        prev = hist.iloc[-2]

        price = round(last['Close'], 2)
        prev_close = round(prev['Close'], 2)
        pct_change = round((price - prev_close) / prev_close * 100, 2)
        volume = int(last['Volume'])
        avg_volume_30d = int(hist['Volume'].tail(30).mean())
        volume_ratio = round(volume / avg_volume_30d, 2) if avg_volume_30d > 0 else 1.0

        # Support / resistance: use recent lows/highs
        recent = hist.tail(20)
        support = round(recent['Low'].min(), 2)
        resistance = round(recent['High'].max(), 2)

        # 50-day simple MA
        ma50 = round(hist['Close'].tail(50).mean(), 2) if len(hist) >= 50 else None

        # Analyst target
        analyst_target = info.get('targetMeanPrice') or info.get('targetHighPrice')
        if analyst_target:
            analyst_target = round(float(analyst_target), 2)

        # Premarket price & gap
        pre_price = info.get('preMarketPrice') or info.get('postMarketPrice')
        pre_gap = None
        if pre_price and price:
            pre_price = round(float(pre_price), 2)
            pre_gap  = round((pre_price - price) / price * 100, 2)

        return {
            'ticker': ticker,
            'price': price,
            'prev_close': prev_close,
            'pct_change': pct_change,
            'pre_price': pre_price,
            'pre_gap': pre_gap,
            'website': info.get('website', ''),
            'volume': volume,
            'avg_volume_30d': avg_volume_30d,
            'volume_ratio': volume_ratio,
            'support': support,
            'resistance': resistance,
            'ma50': ma50,
            'analyst_target': analyst_target,
            'market_cap': info.get('marketCap'),
            'sector': info.get('sector', ''),
            'name': info.get('shortName', ticker),
        }
    except Exception as e:
        return {'ticker': ticker, 'error': str(e)}


# ---------------------------------------------------------------------------
# Logo downloader — caches to data/logos/
# ---------------------------------------------------------------------------

LOGO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'logos')

def download_logo(ticker: str, website: str) -> str | None:
    """
    Fetch company logo via Google favicon API using the company website domain.
    Caches to data/logos/. Returns local file path or None.
    """
    if not website:
        return None
    os.makedirs(LOGO_DIR, exist_ok=True)
    path = os.path.join(LOGO_DIR, f'{ticker}.png')
    if os.path.exists(path):
        return path
    try:
        # Extract bare domain from full URL
        domain = website.replace('https://', '').replace('http://', '').split('/')[0]
        url = f'https://www.google.com/s2/favicons?domain={domain}&sz=128'
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200 and len(r.content) > 500:
            with open(path, 'wb') as f:
                f.write(r.content)
            return path
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# 3-source price cross-reference
# ---------------------------------------------------------------------------

def get_yahoo_price(ticker: str) -> float | None:
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period='1d')
        if not hist.empty:
            return round(hist['Close'].iloc[-1], 2)
    except Exception:
        pass
    return None


def get_finviz_price(ticker: str) -> float | None:
    try:
        url = f'https://finviz.com/quote.ashx?t={ticker}'
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, 'lxml')
        price_el = soup.find('strong', {'class': 'quote-price_wrapper_price'})
        if not price_el:
            # try alternate selector
            price_el = soup.select_one('table.snapshot-table2 tr td.snapshot-td2 b')
        if price_el:
            return round(float(price_el.get_text(strip=True).replace(',', '')), 2)
    except Exception:
        pass
    return None


def get_wsj_price(ticker: str) -> float | None:
    """Wall Street Journal as third source."""
    try:
        url = f'https://www.wsj.com/market-data/quotes/{ticker}'
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, 'lxml')
        el = soup.select_one('span[class*="WSJTheme--last"]')
        if el:
            return round(float(el.get_text(strip=True).replace(',', '')), 2)
    except Exception:
        pass
    return None


def cross_reference_price(ticker: str) -> dict:
    yahoo = get_yahoo_price(ticker)
    finviz = get_finviz_price(ticker)
    wsj = get_wsj_price(ticker)

    prices = [p for p in [yahoo, finviz, wsj] if p is not None]
    consensus = round(sum(prices) / len(prices), 2) if prices else None

    return {
        'yahoo': yahoo,
        'finviz': finviz,
        'wsj': wsj,
        'consensus': consensus,
        'sources_agree': len(prices) >= 2 and (max(prices) - min(prices)) < 0.50 if prices else False,
    }


# ---------------------------------------------------------------------------
# News headlines via Finnhub
# ---------------------------------------------------------------------------

def get_news(ticker: str, max_items: int = 5) -> list:
    try:
        import finnhub
        client = finnhub.Client(api_key='')  # free tier, no key needed for basic news
        today = date.today().strftime('%Y-%m-%d')
        news = client.company_news(ticker, _from=today, to=today)
        return [
            {'headline': n['headline'], 'source': n['source'], 'url': n['url']}
            for n in news[:max_items]
        ]
    except Exception:
        return _get_news_yahoo(ticker, max_items)


def _get_news_yahoo(ticker: str, max_items: int = 5) -> list:
    try:
        t = yf.Ticker(ticker)
        news = t.news or []
        return [
            {'headline': n.get('content', {}).get('title', ''), 'source': 'Yahoo Finance', 'url': ''}
            for n in news[:max_items]
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Options flow — unusual call/put volume vs open interest
# ---------------------------------------------------------------------------

def get_options_flow(ticker: str) -> dict:
    """
    Returns a summary of unusual options activity using yfinance.
    Looks at the nearest expiry: flags if call or put volume is >2x open interest.
    """
    try:
        t = yf.Ticker(ticker)
        exps = t.options
        if not exps:
            return {}

        chain = t.option_chain(exps[0])
        calls = chain.calls
        puts  = chain.puts

        call_vol = int(calls['volume'].sum()) if 'volume' in calls.columns else 0
        put_vol  = int(puts['volume'].sum())  if 'volume' in puts.columns  else 0
        call_oi  = int(calls['openInterest'].sum()) if 'openInterest' in calls.columns else 1
        put_oi   = int(puts['openInterest'].sum())  if 'openInterest' in puts.columns  else 1

        call_ratio = round(call_vol / call_oi, 2) if call_oi > 0 else 0
        put_ratio  = round(put_vol  / put_oi,  2) if put_oi  > 0 else 0
        pc_ratio   = round(put_vol  / call_vol, 2) if call_vol > 0 else None

        unusual = None
        if call_ratio > 2.0:
            unusual = f'Unusual CALLS {call_ratio}x OI'
        elif put_ratio > 2.0:
            unusual = f'Unusual PUTS {put_ratio}x OI'

        return {
            'call_vol': call_vol,
            'put_vol': put_vol,
            'call_oi': call_oi,
            'put_oi': put_oi,
            'call_ratio': call_ratio,
            'put_ratio': put_ratio,
            'pc_ratio': pc_ratio,
            'unusual': unusual,
            'expiry': exps[0],
        }
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Earnings calendar — upcoming earnings within N days
# ---------------------------------------------------------------------------

def get_earnings_dates(tickers: list, days_ahead: int = 5) -> dict:
    """
    For each ticker, check if earnings are within days_ahead trading days.
    Returns dict of ticker -> {'date': str, 'days_away': int, 'time': 'BMO'|'AMC'|'?'}
    """
    from datetime import timedelta
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    results = {}

    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            cal = t.calendar
            if cal is None:
                continue
            # calendar can be a dict or DataFrame depending on yfinance version
            if hasattr(cal, 'to_dict'):
                cal = cal.to_dict()
            earn_date = None
            if isinstance(cal, dict):
                earn_date = cal.get('Earnings Date') or cal.get('earningsDate')
                if isinstance(earn_date, list):
                    earn_date = earn_date[0] if earn_date else None
            if earn_date is None:
                continue
            # normalise to date
            if hasattr(earn_date, 'date'):
                earn_date = earn_date.date()
            elif isinstance(earn_date, str):
                earn_date = date.fromisoformat(earn_date[:10])
            if today <= earn_date <= cutoff:
                days_away = (earn_date - today).days
                results[ticker] = {
                    'date': earn_date.strftime('%b %d'),
                    'days_away': days_away,
                }
        except Exception:
            continue

    return results


# ---------------------------------------------------------------------------
# Market-wide headlines (broad macro + top movers news)
# ---------------------------------------------------------------------------

def get_market_headlines(max_items: int = 7) -> list:
    """Pull today's top market-moving headlines from Yahoo Finance general news."""
    headlines = []

    # 1. Yahoo Finance market news RSS
    try:
        url = 'https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,^IXIC,^DJI&region=US&lang=en-US'
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, 'lxml-xml')
        for item in soup.find_all('item')[:max_items]:
            title = item.find('title')
            source = item.find('source')
            if title and title.get_text(strip=True):
                headlines.append({
                    'headline': title.get_text(strip=True),
                    'source': source.get_text(strip=True) if source else 'Yahoo Finance',
                })
    except Exception:
        pass

    # 2. Fallback: yfinance news for SPY and QQQ
    if len(headlines) < 4:
        for ticker in ['SPY', 'QQQ']:
            try:
                t = yf.Ticker(ticker)
                news = t.news or []
                for n in news[:4]:
                    headline = n.get('content', {}).get('title', '')
                    if headline and headline not in [h['headline'] for h in headlines]:
                        headlines.append({'headline': headline, 'source': 'Yahoo Finance'})
                        if len(headlines) >= max_items:
                            break
            except Exception:
                pass
            if len(headlines) >= max_items:
                break

    return headlines[:max_items]


# ---------------------------------------------------------------------------
# Full market snapshot
# ---------------------------------------------------------------------------

def get_market_snapshot() -> dict:
    print('  Fetching Fear & Greed...')
    fg = get_fear_greed()

    print('  Fetching treasury yields...')
    yields = get_treasury_yields()

    print('  Fetching economic events...')
    events = get_economic_events()

    print('  Fetching market headlines...')
    headlines = get_market_headlines()

    print('  Scanning Finviz movers...')
    gainers = get_finviz_movers()
    losers = get_finviz_losers()

    # Build candidate universe: core watchlist + finviz movers (deduplicated)
    candidates = list(dict.fromkeys(CORE_WATCHLIST + gainers[:20] + losers[:10]))
    # Filter out penny stocks (price < $5) — done inside get_ticker_data via yfinance
    candidates = [c for c in candidates if c and len(c) <= 5 and c.isalpha()]

    print(f'  Fetching ticker data for {len(candidates)} candidates...')
    ticker_data = []
    for i, ticker in enumerate(candidates):
        data = get_ticker_data(ticker)
        if data and 'price' in data and data['price'] >= 5:
            ticker_data.append(data)
        if i % 10 == 0 and i > 0:
            time.sleep(0.5)  # gentle rate limiting

    # Cache logos for all tickers that have a website
    print('  Caching logos...')
    for t in ticker_data:
        if t.get('website'):
            local = download_logo(t['ticker'], t['website'])
            if local:
                t['logo_path'] = local

    # Options flow for top movers only (limit to keep runtime reasonable)
    print('  Fetching options flow for top candidates...')
    top_tickers = [t['ticker'] for t in sorted(ticker_data, key=lambda x: x.get('volume_ratio', 0), reverse=True)[:20]]
    options_flow = {}
    for ticker in top_tickers:
        flow = get_options_flow(ticker)
        if flow:
            options_flow[ticker] = flow
        time.sleep(0.2)

    # Always fetch QQQ and SPY as index reference (guaranteed, not dependent on movers)
    print('  Fetching QQQ/SPY index data...')
    index_data = {}
    for sym in ['QQQ', 'SPY']:
        d = get_ticker_data(sym)
        if d:
            index_data[sym] = d

    return {
        'date': date.today().strftime('%Y-%m-%d'),
        'fear_greed': fg,
        'yields': yields,
        'economic_events': events,
        'market_headlines': headlines,
        'tickers': ticker_data,
        'options_flow': options_flow,
        'gainers_list': gainers[:15],
        'losers_list': losers[:10],
        'index_data': index_data,
    }


if __name__ == '__main__':
    snap = get_market_snapshot()
    print(json.dumps(snap, indent=2, default=str))
