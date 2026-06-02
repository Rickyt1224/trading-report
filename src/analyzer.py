"""
Claude API analysis module.
Sends market snapshot to Claude, gets top 10 trade setups with if/then statements.
"""

import os
import json
import anthropic
from datetime import date
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'), override=True)

def _client():
    return anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

MORNING_SYSTEM_PROMPT = """You are an expert day trader and technical analyst preparing a pre-market trading report.
Your job is to select the 10 best trade opportunities for today and present them clearly and concisely.

Rules:
- No penny stocks (price must be >$5)
- Focus on stocks/ETFs with clear catalysts, high relative volume, or strong technical setups
- Prioritize QQQ holdings and tech sector, but include broad movers with strong setups
- Each trade must have a specific if/then entry trigger, not vague guidance
- Be realistic about risk — include stop levels
- Use the macro context (Fear & Greed, yields, economic events) to frame directional bias
- ALWAYS return exactly 5 Long trades and 5 Short trades (10 total). No exceptions.
- ALL targets are for DAY TRADING — intraday or at most end-of-week. No long-term price targets.
- intraday_target must be a realistic same-day or at-most-5-day technical level (next resistance for longs, next support for shorts). Never use analyst consensus price targets.

ENTRY TIMING RULES (approved 2026-06-01):
- Require the first 15-minute candle to CLOSE above the trigger level before entering a long. If the candle closes below trigger, skip the trade regardless of open price.

CATALYST FILTER RULES (approved 2026-06-01):
- Sympathy/sector plays (no direct earnings catalyst) must gap at least 2% above prior close AND above the trigger level to qualify. If gap is less than 2% or trigger is not cleared at open, skip entirely. Flag sympathy plays with reduced position size (50% of direct-catalyst size).

STOP PLACEMENT RULES (approved 2026-06-01):
- For short entries: stop must be set at pre-market swing high PLUS $0.50 buffer, not a fixed round-number level.
- For long gap plays: stop must be set below the first 15-minute candle LOW, not at a pre-determined level set before market open.

EXIT / TARGET RULES (approved 2026-06-01):
- For earnings gap plays where the overnight gap exceeds 15%: use tiered exits — exit 40% at initial target, 40% at initial target ×2, trail final 20% with a 5-minute swing-low trailing stop. For non-catalyst plays, maintain single fixed targets.

VOLUME FILTER RULES (approved 2026-06-01):
- If projected daily volume exceeds 3× normal AND stock has gapped more than 5% pre-market: treat as scalp only — mandatory full exit at first target, no runners.
- If a stock's volume exceeds 5× average AND price is below $15: exclude from the call list entirely (meme/speculative volatility makes standard stops invalid).

MACRO FILTER RULES (approved 2026-06-01):
- When overall bias is Bullish (Fear & Greed > 55): reduce position size on medium-conviction shorts by 30% and tighten their profit target by 20%. Only High-conviction shorts with confirmed stock-specific negative catalysts should be held to full target in a bullish tape.

Output format: Return ONLY valid JSON matching this exact structure:
{
  "market_bias": "Bullish|Bearish|Neutral",
  "bias_reason": "1-2 sentence macro summary",
  "key_risks": "1 sentence on biggest risk today",
  "trades": [
    {
      "rank": 1,
      "ticker": "NVDA",
      "name": "NVIDIA Corporation",
      "type": "Long|Short",
      "price": 925.50,
      "catalyst": "Specific news/reason driving this today",
      "volume_ratio": 2.3,
      "support": 910.00,
      "resistance": 945.00,
      "intraday_target": 940.00,
      "if_then": "IF NVDA holds above $915 in the first 15 minutes and volume remains above 2x average, THEN enter long targeting $940 intraday, stop at $908.",
      "secondary_trigger": "IF NVDA breaks above $930 with volume spike, THEN add to position targeting $950 by end of day.",
      "avoid_if": "Avoid if QQQ opens red and NVDA breaks below $910.",
      "conviction": "High|Medium|Low",
      "price_sources": {"yahoo": 925.50, "finviz": 925.75, "wsj": 925.40}
    }
  ]
}"""


AFTERMARKET_SYSTEM_PROMPT = """You are an expert trading analyst reviewing your pre-market trade calls after market close.
Your job is to objectively assess what worked, what failed, and WHY — then suggest specific rule improvements.

Be honest and self-critical. The goal is to improve the system over time.

Output format: Return ONLY valid JSON matching this exact structure:
{
  "overall_accuracy": "X/10 trades triggered or moved in predicted direction",
  "summary": "2-3 sentence honest assessment of today's calls",
  "trade_reviews": [
    {
      "ticker": "NVDA",
      "predicted_direction": "Long",
      "predicted_entry": 915.00,
      "actual_open": 918.00,
      "actual_high": 935.00,
      "actual_low": 908.00,
      "actual_close": 930.00,
      "if_then_triggered": true,
      "outcome": "Winner|Loser|No trigger|Partial",
      "what_worked": "Catalyst was real, volume confirmed",
      "what_failed": "Stop was too tight given premarket volatility",
      "lesson": "Specific takeaway"
    }
  ],
  "suggested_improvements": [
    {
      "area": "Stop placement|Entry timing|Catalyst filter|Volume filter|Macro filter|Other",
      "current_rule": "What the current rule is",
      "proposed_change": "Specific new rule",
      "reason": "Why this change would improve results"
    }
  ]
}"""


def run_morning_analysis(snapshot: dict) -> dict:
    """Send market snapshot to Claude, return structured trade analysis."""

    # Build a concise but complete prompt from the snapshot
    fg = snapshot.get('fear_greed', {})
    yields = snapshot.get('yields', {})
    events = snapshot.get('economic_events', [])
    tickers = snapshot.get('tickers', [])
    options_flow = snapshot.get('options_flow', {})

    # Sort tickers by volume ratio (highest relative volume first)
    tickers_sorted = sorted(
        [t for t in tickers if 'volume_ratio' in t],
        key=lambda x: x.get('volume_ratio', 0),
        reverse=True
    )

    events_str = '\n'.join([f"  - {e['event']} {e['time']}" for e in events[:6]]) or '  None reported'

    ticker_lines = []
    for t in tickers_sorted[:40]:
        flow = options_flow.get(t['ticker'], {})
        flow_str = ''
        if flow.get('unusual'):
            flow_str = f" | Options: {flow['unusual']} (P/C ratio: {flow.get('pc_ratio', 'N/A')})"
        pre_str = ''
        if t.get('pre_price'):
            pre_str = f" | Premarket: ${t['pre_price']} ({t.get('pre_gap', 0):+.1f}%)"
        line = (
            f"  {t['ticker']} ({t.get('name', '')}) | "
            f"Price: ${t['price']} ({t['pct_change']:+.1f}%) | "
            f"Vol ratio: {t.get('volume_ratio', 'N/A')}x | "
            f"Support: ${t.get('support', 'N/A')} | "
            f"Resistance: ${t.get('resistance', 'N/A')} | "
            f"MA50: ${t.get('ma50', 'N/A')}"
            f"{pre_str}{flow_str}"
        )
        ticker_lines.append(line)

    prompt = f"""Today is {snapshot['date']}. Pre-market analysis request.

MACRO CONTEXT:
- Fear & Greed Index: {fg.get('score', 'N/A')} ({fg.get('rating', 'N/A')})
- 2Y Treasury Yield: {yields.get('2Y', {}).get('value', 'N/A')}% (chg: {yields.get('2Y', {}).get('change', 'N/A')})
- 10Y Treasury Yield: {yields.get('10Y', {}).get('value', 'N/A')}% (chg: {yields.get('10Y', {}).get('change', 'N/A')})
- 30Y Treasury Yield: {yields.get('30Y', {}).get('value', 'N/A')}% (chg: {yields.get('30Y', {}).get('change', 'N/A')})

TODAY'S ECONOMIC EVENTS:
{events_str}

TOP MOVERS BY RELATIVE VOLUME (sorted highest vol ratio first):
{chr(10).join(ticker_lines)}

INSTRUCTIONS:
Select exactly 10 trade setups: 5 Long and 5 Short. No more, no fewer of each.
Prioritize:
1. High relative volume (>1.5x) with clear catalyst
2. QQQ / tech sector names
3. Strong technical setup (near support for longs, near resistance for shorts)
4. ETFs for broader market plays (QQQ, TQQQ, SPY, XLK, SOXX)

For Short candidates: look for stocks near resistance, extended moves, negative catalysts, or weak macro setups.
Rank the 5 Longs first (ranks 1-5), then the 5 Shorts (ranks 6-10).

Return the JSON as specified."""

    response = _client().messages.create(
        model='claude-sonnet-4-6',
        max_tokens=4096,
        system=MORNING_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith('```'):
        raw = re.sub(r'^```[a-z]*\n?', '', raw)
        raw = re.sub(r'\n?```$', '', raw)

    result = json.loads(raw)

    # Enforce 5 Long / 5 Short — trim extras if Claude over-generates
    trades = result.get('trades', [])
    longs  = [t for t in trades if t.get('type') == 'Long'][:5]
    shorts = [t for t in trades if t.get('type') == 'Short'][:5]
    result['trades'] = longs + shorts

    return result


def run_aftermarket_analysis(morning_analysis: dict, eod_data: dict) -> dict:
    """Compare morning predictions vs actual EOD price action."""

    trades_summary = []
    for trade in morning_analysis.get('trades', []):
        ticker = trade['ticker']
        eod = eod_data.get(ticker, {})
        trades_summary.append({
            'ticker': ticker,
            'type': trade['type'],
            'predicted_entry': trade.get('support') if trade['type'] == 'Long' else trade.get('resistance'),
            'if_then': trade['if_then'],
            'conviction': trade['conviction'],
            'actual_open': eod.get('open'),
            'actual_high': eod.get('high'),
            'actual_low': eod.get('low'),
            'actual_close': eod.get('close'),
            'actual_volume': eod.get('volume'),
        })

    prompt = f"""Today is {morning_analysis.get('date', 'today')}. Post-market review.

ORIGINAL MARKET BIAS: {morning_analysis.get('market_bias')} — {morning_analysis.get('bias_reason')}

MORNING TRADE CALLS VS ACTUAL RESULTS:
{json.dumps(trades_summary, indent=2)}

Review each trade objectively. Identify patterns in what worked and failed.
Suggest specific, actionable rule improvements — not vague observations.
Return the JSON as specified."""

    response = _client().messages.create(
        model='claude-sonnet-4-6',
        max_tokens=8192,
        system=AFTERMARKET_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```[a-z]*\n?', '', raw)
        raw = re.sub(r'\n?```$', '', raw)

    # Attempt to recover truncated JSON by closing open structures
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to salvage by truncating to last complete object/array boundary
        for end_char in ('}', ']'):
            idx = raw.rfind(end_char)
            if idx != -1:
                candidate = raw[:idx + 1]
                # Close any unclosed outer braces
                opens  = candidate.count('{') - candidate.count('}')
                closes = candidate.count('[') - candidate.count(']')
                candidate += ']' * closes + '}' * opens
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue
        raise


import re  # ensure re is available for JSON cleaning
