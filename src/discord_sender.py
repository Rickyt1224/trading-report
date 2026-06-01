"""
Discord webhook sender — morning report only.
Sends a summary embed + PDF attachment to the configured channel.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'), override=True)

WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL', '')


def send_morning_report(pdf_path: str, analysis: dict, snapshot: dict) -> bool:
    """
    Post morning report to Discord with a summary embed and PDF attachment.
    Returns True on success.
    """
    if not WEBHOOK_URL:
        return False

    today      = snapshot.get('date', '')
    bias       = analysis.get('market_bias', 'N/A')
    bias_reason= analysis.get('bias_reason', '')
    key_risks  = analysis.get('key_risks', '')
    fg         = snapshot.get('fear_greed', {})
    yields     = snapshot.get('yields', {})
    trades     = analysis.get('trades', [])

    # Bias colour for embed sidebar
    bias_color = 0x1A7F37 if 'Bull' in bias else (0xCF222E if 'Bear' in bias else 0xFFD700)

    # Top picks line
    top_tickers = ', '.join(
        '**{}** ({})'.format(t['ticker'], t.get('type', '')[:1])
        for t in trades[:5]
    )

    # Treasury yields
    y10 = yields.get('10Y', {})
    y2  = yields.get('2Y', {})

    embed = {
        'title': f'📊  Daily Trade Report  —  {today}',
        'color': bias_color,
        'fields': [
            {
                'name': '🧭  Market Bias',
                'value': f'**{bias}**  —  {bias_reason}',
                'inline': False,
            },
            {
                'name': '😨  Fear & Greed',
                'value': f'{fg.get("score","N/A")} — {fg.get("rating","N/A")}',
                'inline': True,
            },
            {
                'name': '📈  10Y Yield',
                'value': f'{y10.get("value","N/A")}%  ({y10.get("change",0):+.3f})',
                'inline': True,
            },
            {
                'name': '📈  2Y Yield',
                'value': f'{y2.get("value","N/A")}%  ({y2.get("change",0):+.3f})',
                'inline': True,
            },
            {
                'name': '🔝  Top 5 Picks',
                'value': top_tickers or 'See report',
                'inline': False,
            },
            {
                'name': '⚠️  Key Risk',
                'value': key_risks or '—',
                'inline': False,
            },
        ],
        'footer': {'text': 'For informational purposes only — not financial advice.'},
    }

    try:
        with open(pdf_path, 'rb') as f:
            response = requests.post(
                WEBHOOK_URL,
                data={'payload_json': __import__('json').dumps({'embeds': [embed]})},
                files={'file': (os.path.basename(pdf_path), f, 'application/pdf')},
                timeout=30,
            )
        if response.status_code in (200, 204):
            return True
        else:
            import logging
            logging.getLogger(__name__).error(
                f'Discord send failed: {response.status_code} {response.text}'
            )
            return False
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'Discord send error: {e}')
        return False
