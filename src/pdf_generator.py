"""
PDF report generator for morning and aftermarket reports.
Clean professional layout — white background, color-coded accents.
"""

import os
import math
from datetime import date
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen.canvas import Canvas
from reportlab.graphics.shapes import (
    Drawing, Wedge, Circle, Line, String, Rect, Group
)
from reportlab.graphics import renderPDF
from reportlab.platypus.flowables import Flowable

# Color palette — professional light theme
BG_WHITE      = colors.white
BG_LIGHT      = colors.HexColor('#F6F8FA')   # alternating row
BG_HEADER     = colors.HexColor('#1C2128')   # dark header rows
BG_TITLE_BAR  = colors.HexColor('#0D1117')   # page title bar

TEXT_DARK     = colors.HexColor('#1A1A2E')
TEXT_MED      = colors.HexColor('#444444')
TEXT_LIGHT    = colors.HexColor('#666666')
TEXT_WHITE    = colors.white

GREEN         = colors.HexColor('#1A7F37')
RED           = colors.HexColor('#CF222E')
BLUE          = colors.HexColor('#0969DA')
GOLD          = colors.HexColor('#9A6700')
ORANGE        = colors.HexColor('#BC4C00')
BORDER        = colors.HexColor('#D0D7DE')

REPORTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'reports')


def _versioned_path(base_path: str) -> str:
    """If base_path exists, return base_path with _rev02, _rev03, etc."""
    if not os.path.exists(base_path):
        return base_path
    root, ext = os.path.splitext(base_path)
    # strip any existing _rev## suffix before adding new one
    import re as _re
    root = _re.sub(r'_rev\d+$', '', root)
    rev = 2
    while os.path.exists(f'{root}_rev{rev:02d}{ext}'):
        rev += 1
    return f'{root}_rev{rev:02d}{ext}'

# ── Fear & Greed gauge zones ───────────────────────────────────────────────
_ZONES = [
    (0,  25,  colors.HexColor('#C0392B'), 'Extreme Fear'),
    (25, 46,  colors.HexColor('#E67E22'), 'Fear'),
    (46, 54,  colors.HexColor('#F1C40F'), 'Neutral'),
    (54, 75,  colors.HexColor('#27AE60'), 'Greed'),
    (75, 100, colors.HexColor('#1A5C38'), 'Extreme Greed'),
]


class FearGreedGauge(Flowable):
    """Semicircle gauge for the Fear & Greed score (0–100)."""

    def __init__(self, score, rating, width=1.9*inch, height=1.05*inch):
        super().__init__()
        self.score   = score if isinstance(score, (int, float)) else 50
        self.rating  = rating or ''
        self.width   = width
        self.height  = height

    def wrap(self, *args):
        return self.width, self.height

    def draw(self):
        c   = self.canv
        cx  = self.width / 2
        cy  = 0.18 * inch          # baseline of semicircle
        r_outer = self.width * 0.44
        r_inner = r_outer * 0.58   # donut thickness

        # --- draw colored wedge zones ---
        for lo, hi, color, _ in _ZONES:
            # angles: score 0 → 180°, score 100 → 0°  (counterclockwise left-to-right)
            a_start = 180 - (hi / 100 * 180)
            a_end   = 180 - (lo / 100 * 180)
            c.saveState()
            c.setFillColor(color)
            c.setStrokeColor(colors.white)
            c.setLineWidth(0.8)
            # outer arc path
            p = c.beginPath()
            p.moveTo(
                cx + r_outer * math.cos(math.radians(a_start)),
                cy + r_outer * math.sin(math.radians(a_start)),
            )
            p.arcTo(cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer,
                    a_start, a_end - a_start)
            p.lineTo(
                cx + r_inner * math.cos(math.radians(a_end)),
                cy + r_inner * math.sin(math.radians(a_end)),
            )
            p.arcTo(cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner,
                    a_end, a_start - a_end)
            p.close()
            c.drawPath(p, fill=1, stroke=1)
            c.restoreState()

        # --- needle ---
        needle_angle = math.radians(180 - (self.score / 100 * 180))
        nx = cx + r_inner * 0.85 * math.cos(needle_angle)
        ny = cy + r_inner * 0.85 * math.sin(needle_angle)
        c.saveState()
        c.setStrokeColor(colors.HexColor('#1A1A2E'))
        c.setLineWidth(1.8)
        c.setLineCap(1)
        c.line(cx, cy, nx, ny)
        c.restoreState()

        # center pivot dot
        c.saveState()
        c.setFillColor(colors.HexColor('#1A1A2E'))
        c.circle(cx, cy, 3.5, fill=1, stroke=0)
        c.restoreState()

        # --- score text ---
        c.saveState()
        c.setFont('Helvetica-Bold', 13)
        c.setFillColor(colors.HexColor('#1A1A2E'))
        score_str = str(int(round(self.score)))
        c.drawCentredString(cx, cy + r_inner * 0.20, score_str)
        c.setFont('Helvetica', 6.5)
        c.setFillColor(colors.HexColor('#666666'))
        c.drawCentredString(cx, cy + r_inner * 0.20 - 9, self.rating.upper())
        c.restoreState()

        # --- label at bottom ---
        c.saveState()
        c.setFont('Helvetica-Bold', 6.5)
        c.setFillColor(colors.HexColor('#444444'))
        c.drawCentredString(cx, 2, 'FEAR & GREED')
        c.restoreState()


def _styles():
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle('title', parent=base['Normal'],
                                fontSize=16, textColor=TEXT_WHITE, fontName='Helvetica-Bold',
                                alignment=TA_CENTER, spaceAfter=0),
        'subtitle': ParagraphStyle('subtitle', parent=base['Normal'],
                                   fontSize=8, textColor=TEXT_LIGHT, fontName='Helvetica',
                                   alignment=TA_CENTER, spaceAfter=4),
        'section': ParagraphStyle('section', parent=base['Normal'],
                                  fontSize=9, textColor=BLUE, fontName='Helvetica-Bold',
                                  spaceBefore=4, spaceAfter=2),
        'body': ParagraphStyle('body', parent=base['Normal'],
                               fontSize=8, textColor=TEXT_DARK, fontName='Helvetica', leading=11),
        'small': ParagraphStyle('small', parent=base['Normal'],
                                fontSize=7, textColor=TEXT_MED, fontName='Helvetica', leading=10),
        'if_then': ParagraphStyle('if_then', parent=base['Normal'],
                                  fontSize=7.5, textColor=TEXT_DARK, fontName='Helvetica-Bold',
                                  leading=11, leftIndent=2),
        'catalyst': ParagraphStyle('catalyst', parent=base['Normal'],
                                   fontSize=7, textColor=BLUE, fontName='Helvetica',
                                   leading=10, leftIndent=2),
        'avoid': ParagraphStyle('avoid', parent=base['Normal'],
                                fontSize=7, textColor=RED, fontName='Helvetica',
                                leading=10, leftIndent=2),
        'sources': ParagraphStyle('sources', parent=base['Normal'],
                                  fontSize=6.5, textColor=TEXT_LIGHT, fontName='Helvetica',
                                  leading=9, leftIndent=2),
    }


def _bias_color(bias: str):
    if 'Bull' in bias:  return GREEN
    if 'Bear' in bias:  return RED
    return GOLD


def _conviction_color(conviction: str):
    return {'High': GREEN, 'Medium': GOLD, 'Low': RED}.get(conviction, TEXT_DARK)


class _PageBackground(Canvas):
    """Draws a dark title-bar band at the top of each page."""
    BAND_HEIGHT = 0.55 * inch

    def showPage(self):
        w, h = self._pagesize
        self.saveState()
        self.setFillColor(BG_TITLE_BAR)
        self.rect(0, h - self.BAND_HEIGHT, w, self.BAND_HEIGHT, fill=1, stroke=0)
        self.restoreState()
        super().showPage()


def build_morning_pdf(analysis: dict, snapshot: dict, output_path: str = None,
                      charts_flowables: list = None) -> str:
    today = snapshot.get('date', date.today().strftime('%Y-%m-%d'))
    if output_path is None:
        output_path = _versioned_path(os.path.join(REPORTS_DIR, f'{today}_morning.pdf'))
    os.makedirs(REPORTS_DIR, exist_ok=True)

    BAND = _PageBackground.BAND_HEIGHT

    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(letter),
        leftMargin=0.4 * inch,
        rightMargin=0.4 * inch,
        topMargin=BAND + 0.1 * inch,
        bottomMargin=0.25 * inch,
    )

    s = _styles()
    story = []

    bias    = analysis.get('market_bias', 'Neutral')
    fg      = snapshot.get('fear_greed', {})
    yields  = snapshot.get('yields', {})
    y10     = yields.get('10Y', {})
    y2      = yields.get('2Y', {})

    # Title sits inside the dark band via top margin offset — draw as white text
    story.append(Paragraph(f'DAILY TRADE REPORT  ·  {today}', s['title']))
    story.append(Paragraph('Pre-Market Analysis  |  Top 10 Trade Setups', s['subtitle']))

    # ── Macro section: gauge left + news/events right ─────────────────────
    fg_score  = fg.get('score', 'N/A')
    fg_rating = fg.get('rating', 'N/A')
    bias_col  = _bias_color(bias)

    gauge = FearGreedGauge(fg_score, fg_rating)

    # yield arrow helper
    def _yield_str(y):
        val = y.get('value', 'N/A')
        chg = y.get('change', 0) or 0
        arrow = '▲' if chg > 0 else ('▼' if chg < 0 else '—')
        c = RED if chg > 0 else (GREEN if chg < 0 else TEXT_MED)
        return f'{val}%  {arrow}{abs(chg):.3f}', c

    y30 = yields.get('30Y', {})
    y10s, y10c = _yield_str(y10)
    y2s,  y2c  = _yield_str(y2)
    y30s, y30c = _yield_str(y30)

    bias_reason = analysis.get('bias_reason', '')
    key_risks   = analysis.get('key_risks', '')

    # Text styles for the right panel
    label_s  = ParagraphStyle('rl', fontSize=6.5, textColor=TEXT_LIGHT,
                               fontName='Helvetica-Bold')
    val_s    = ParagraphStyle('rv', fontSize=8,   textColor=TEXT_DARK,
                               fontName='Helvetica-Bold')
    news_hdr = ParagraphStyle('nh', fontSize=6.5, textColor=BLUE,
                               fontName='Helvetica-Bold', spaceBefore=3)
    news_s   = ParagraphStyle('ns', fontSize=7.5, textColor=TEXT_DARK,
                               fontName='Helvetica', leading=10, leftIndent=6)
    event_s  = ParagraphStyle('es', fontSize=7.5, textColor=GOLD,
                               fontName='Helvetica', leading=10, leftIndent=6)

    # Build right-panel content list
    right = []

    # Bias + yields on one line each
    right.append(Paragraph(
        f'<b><font color="{bias_col.hexval() if hasattr(bias_col,"hexval") else "#1A7F37"}">'
        f'Bias: {bias}</font></b>  ·  '
        f'<b>10Y:</b> {y10s}  ·  <b>2Y:</b> {y2s}  ·  <b>30Y:</b> {y30s}',
        ParagraphStyle('biasline', fontSize=8, textColor=TEXT_DARK,
                       fontName='Helvetica', leading=11)
    ))
    right.append(Paragraph(
        f'<b>Outlook:</b> {bias_reason}  '
        f'<font color="#CF222E"><b>  Risk:</b> {key_risks}</font>',
        ParagraphStyle('ol', fontSize=7.5, textColor=TEXT_DARK,
                       fontName='Helvetica', leading=10, spaceBefore=2)
    ))

    # Economic events
    events   = snapshot.get('economic_events', [])
    headlines = snapshot.get('market_headlines', [])

    if events:
        right.append(Paragraph('ECONOMIC EVENTS TODAY', news_hdr))
        for ev in events[:3]:
            t_str = ev.get('time', '')
            right.append(Paragraph(
                f'· {ev["event"]}' + (f'  <font color="#666666">({t_str})</font>' if t_str else ''),
                event_s
            ))

    if headlines:
        right.append(Paragraph('MARKET HEADLINES', news_hdr))
        for h in headlines[:4]:
            src  = h.get('source', '')
            text = h.get('headline', '')
            if text:
                right.append(Paragraph(
                    f'· {text}' + (f'  <font color="#666666">[{src}]</font>' if src else ''),
                    news_s
                ))

    # Layout: gauge (left) | news block (right)
    macro_layout = Table(
        [[gauge, right]],
        colWidths=[2.05 * inch, 8.75 * inch],
    )
    macro_layout.setStyle(TableStyle([
        ('ALIGN',        (0, 0), (0, 0), 'CENTER'),
        ('ALIGN',        (1, 0), (1, 0), 'LEFT'),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND',   (1, 0), (1, 0), BG_LIGHT),
        ('BOX',          (1, 0), (1, 0), 1, BORDER),
        ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING',   (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 4),
    ]))
    story.append(macro_layout)
    story.append(Spacer(1, 4))

    # ── Index snapshot bar: QQQ + SPY ──────────────────────────────────────
    index_data = snapshot.get('index_data', {})
    _idx_lbl = ParagraphStyle('idxl', fontSize=6.5, fontName='Helvetica-Bold',
                               textColor=TEXT_LIGHT, alignment=TA_CENTER)
    _idx_val = ParagraphStyle('idxv', fontSize=9,   fontName='Helvetica-Bold',
                               textColor=TEXT_DARK,  alignment=TA_CENTER)
    _idx_chg = ParagraphStyle('idxc', fontSize=8,   fontName='Helvetica-Bold',
                               alignment=TA_CENTER)

    def _index_cell(sym):
        d = index_data.get(sym, {})
        price     = d.get('price', 'N/A')
        pct       = d.get('pct_change')
        pre_price = d.get('pre_price')
        pre_gap   = d.get('pre_gap')
        ma50      = d.get('ma50')
        support   = d.get('support')
        resist    = d.get('resistance')

        chg_str   = f'{pct:+.2f}%' if pct is not None else '—'
        chg_color = GREEN.hexval() if (pct or 0) >= 0 else RED.hexval()
        pre_str   = f'Pre: ${pre_price}  ({pre_gap:+.1f}%)' if pre_price and pre_gap is not None else ''
        lvl_str   = ''
        if support and resist:
            lvl_str = f'S ${support}  ·  R ${resist}'
        if ma50:
            lvl_str += f'  ·  MA50 ${ma50}'

        return [
            Paragraph(sym, _idx_lbl),
            Paragraph(f'${price}', _idx_val),
            Paragraph(f'<font color="{chg_color}">{chg_str}</font>', _idx_chg),
            Paragraph(pre_str,  ParagraphStyle('idxpre', fontSize=7, fontName='Helvetica',
                                               textColor=TEXT_MED, alignment=TA_CENTER)),
            Paragraph(lvl_str, ParagraphStyle('idxlvl', fontSize=6.5, fontName='Helvetica',
                                               textColor=TEXT_LIGHT, alignment=TA_CENTER)),
        ]

    idx_syms = ['QQQ', 'SPY']
    idx_rows = [[item for sym in idx_syms for item in _index_cell(sym)]]
    # 5 cells per symbol × 2 symbols = 10 columns
    idx_col_w = [0.45*inch, 0.65*inch, 0.60*inch, 1.10*inch, 1.85*inch] * len(idx_syms)
    idx_tbl = Table(idx_rows, colWidths=idx_col_w)
    idx_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (4, 0),   colors.HexColor('#EAF5FB')),  # QQQ cols
        ('BACKGROUND',    (5, 0), (9, 0),   BG_LIGHT),                    # SPY cols
        ('LINEAFTER',     (4, 0), (4, 0),   1.5, BORDER),                 # divider between symbols
        ('BOX',           (0, 0), (-1, -1), 1, BORDER),
        ('INNERGRID',     (0, 0), (-1, -1), 0.3, BORDER),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 2),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 2),
    ]))
    story.append(idx_tbl)
    story.append(Spacer(1, 4))

    # ── Trades table ───────────────────────────────────────────────────────
    trades = analysis.get('trades', [])

    col_w = [
        0.20 * inch,   # #
        0.55 * inch,   # ticker
        0.40 * inch,   # dir
        0.52 * inch,   # close
        0.52 * inch,   # pre $
        0.48 * inch,   # gap %
        0.45 * inch,   # chg%
        0.50 * inch,   # vol/avg
        0.50 * inch,   # support
        0.50 * inch,   # resist
        0.60 * inch,   # target
        0.58 * inch,   # conviction
        3.70 * inch,   # if/then
    ]

    th = ParagraphStyle('th', fontSize=7, textColor=TEXT_WHITE,
                        fontName='Helvetica-Bold', alignment=TA_CENTER)

    header = [
        Paragraph('#',           th),
        Paragraph('TICKER',      th),
        Paragraph('DIR',         th),
        Paragraph('CLOSE',       th),
        Paragraph('PRE $',       th),
        Paragraph('GAP %',       th),
        Paragraph('CHG %',       th),
        Paragraph('VOL/AVG',     th),
        Paragraph('SUPPORT',     th),
        Paragraph('RESIST',      th),
        Paragraph('DAY TARGET',   th),
        Paragraph('CONV.',       th),
        Paragraph('IF / THEN  ·  CATALYST  ·  OPTIONS FLOW', th),
    ]

    rows = [header]
    options_flow = snapshot.get('options_flow', {})

    for trade in trades:
        pct       = trade.get('pct_change', 0) or 0
        direction = trade.get('type', 'Long')
        conviction= trade.get('conviction', 'Medium')
        ticker    = trade.get('ticker', '')

        # find premarket data from snapshot tickers
        snap_tick  = next((t for t in snapshot.get('tickers', []) if t.get('ticker') == ticker), {})
        pre_price  = snap_tick.get('pre_price')
        pre_gap    = snap_tick.get('pre_gap')
        logo_path  = snap_tick.get('logo_path')

        c_pct  = ParagraphStyle('cp',  fontSize=8, fontName='Helvetica-Bold',
                                textColor=GREEN if pct >= 0 else RED, alignment=TA_CENTER)
        c_gap  = ParagraphStyle('cg',  fontSize=8, fontName='Helvetica-Bold',
                                textColor=GREEN if (pre_gap or 0) >= 0 else RED, alignment=TA_CENTER)
        c_dir  = ParagraphStyle('cd',  fontSize=8, fontName='Helvetica-Bold',
                                textColor=GREEN if direction == 'Long' else RED, alignment=TA_CENTER)
        c_conv = ParagraphStyle('ccv', fontSize=8, fontName='Helvetica-Bold',
                                textColor=_conviction_color(conviction), alignment=TA_CENTER)
        c8     = ParagraphStyle('c8',  fontSize=8, fontName='Helvetica',
                                textColor=TEXT_DARK, alignment=TA_CENTER)

        pre_price_str = f'${pre_price}' if pre_price else '–'
        pre_gap_str   = f'{pre_gap:+.1f}%' if pre_gap is not None else '–'

        # Build if/then cell content
        cell = []
        catalyst = trade.get('catalyst', '')
        if catalyst:
            cell.append(Paragraph(f'<b>Catalyst:</b> {catalyst}', s['catalyst']))
        cell.append(Paragraph(trade.get('if_then', ''), s['if_then']))
        secondary = trade.get('secondary_trigger', '')
        if secondary:
            cell.append(Paragraph(secondary, s['small']))
        avoid = trade.get('avoid_if', '')
        if avoid:
            cell.append(Paragraph(f'⚠  {avoid}', s['avoid']))

        # Options flow
        flow = options_flow.get(ticker, {})
        if flow:
            unusual = flow.get('unusual', '')
            pc      = flow.get('pc_ratio')
            flow_color = GREEN if 'CALL' in (unusual or '') else (RED if 'PUT' in (unusual or '') else TEXT_MED)
            flow_label = unusual or f'P/C: {pc}'
            cell.append(Paragraph(
                f'Options: {flow_label}' + (f'  |  P/C ratio: {pc}' if unusual and pc else ''),
                ParagraphStyle('fl', fontSize=7, fontName='Helvetica-Bold',
                               textColor=flow_color, leading=10)
            ))

        sources = trade.get('price_sources', {})
        if sources:
            cell.append(Paragraph(
                f"Prices: Yahoo ${sources.get('yahoo','–')}  |  "
                f"Finviz ${sources.get('finviz','–')}  |  "
                f"WSJ ${sources.get('wsj','–')}",
                s['sources']
            ))

        # Ticker cell: logo (if available) + bold ticker name
        tk_style = ParagraphStyle('tk', fontSize=9, fontName='Helvetica-Bold',
                                  textColor=TEXT_DARK, alignment=TA_CENTER)
        if logo_path and os.path.exists(logo_path):
            ticker_cell = [Image(logo_path, width=0.30*inch, height=0.30*inch),
                           Paragraph(f'<b>{ticker}</b>', tk_style)]
        else:
            ticker_cell = Paragraph(f'<b>{ticker}</b>', tk_style)

        rows.append([
            Paragraph(str(trade.get('rank', '')), c8),
            ticker_cell,
            Paragraph(direction, c_dir),
            Paragraph(f'${trade.get("price","N/A")}', c8),
            Paragraph(pre_price_str, c8),
            Paragraph(pre_gap_str, c_gap),
            Paragraph(f'{pct:+.1f}%' if isinstance(pct, (int, float)) else 'N/A', c_pct),
            Paragraph(f'{trade.get("volume_ratio","N/A")}x', c8),
            Paragraph(f'${trade.get("support","N/A")}', c8),
            Paragraph(f'${trade.get("resistance","N/A")}', c8),
            Paragraph(f'${trade.get("intraday_target","N/A")}', c8),
            Paragraph(conviction, c_conv),
            cell,
        ])

    tbl = Table(rows, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0),  (-1, 0),  BG_HEADER),
        ('ROWHEIGHT',     (0, 0),  (-1, 0),  16),
        ('ALIGN',         (0, 0),  (-1, -1), 'CENTER'),
        ('VALIGN',        (0, 0),  (-1, -1), 'TOP'),
        ('BOX',           (0, 0),  (-1, -1), 1, BORDER),
        ('INNERGRID',     (0, 0),  (-1, -1), 0.4, BORDER),
        ('ROWBACKGROUNDS',(0, 1),  (-1, -1), [BG_WHITE, BG_LIGHT]),
        ('LEFTPADDING',   (0, 0),  (-1, -1), 3),
        ('RIGHTPADDING',  (0, 0),  (-1, -1), 3),
        ('TOPPADDING',    (0, 0),  (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0),  (-1, -1), 3),
    ]))
    story.append(tbl)

    # ── Footer ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width='100%', thickness=0.5, color=BORDER))
    story.append(Paragraph(
        f'Generated {date.today().strftime("%B %d, %Y")}  |  '
        'Sources: Yahoo Finance · Finviz · WSJ · CNN Fear & Greed · FRED  |  '
        'For informational purposes only — not financial advice.',
        ParagraphStyle('ft', fontSize=6, textColor=TEXT_LIGHT,
                       fontName='Helvetica', alignment=TA_CENTER)
    ))

    # Append charts as page 2 if provided
    if charts_flowables:
        story.append(PageBreak())
        story.extend(charts_flowables)

    doc.build(story, canvasmaker=_PageBackground)
    return output_path


# ── Aftermarket PDF ────────────────────────────────────────────────────────

def build_aftermarket_pdf(review: dict, date_str: str = None, output_path: str = None) -> str:
    today = date_str or date.today().strftime('%Y-%m-%d')
    if output_path is None:
        output_path = _versioned_path(os.path.join(REPORTS_DIR, f'{today}_aftermarket.pdf'))
    os.makedirs(REPORTS_DIR, exist_ok=True)

    BAND = _PageBackground.BAND_HEIGHT

    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(letter),
        leftMargin=0.4 * inch,
        rightMargin=0.4 * inch,
        topMargin=BAND + 0.1 * inch,
        bottomMargin=0.25 * inch,
    )

    s = _styles()
    story = []

    story.append(Paragraph(f'POST-MARKET REVIEW  ·  {today}', s['title']))
    story.append(Paragraph(
        f'Accuracy: {review.get("overall_accuracy", "N/A")}',
        ParagraphStyle('acc', fontSize=10, textColor=TEXT_WHITE,
                       fontName='Helvetica-Bold', alignment=TA_CENTER)
    ))
    story.append(Spacer(1, 5))
    story.append(Paragraph(review.get('summary', ''), s['body']))
    story.append(Spacer(1, 4))

    # ── QQQ / SPY EOD index bar ────────────────────────────────────────────
    eod_index = review.get('index_eod', {})
    if eod_index:
        _ial = ParagraphStyle('ial2', fontSize=6.5, fontName='Helvetica-Bold',
                               textColor=TEXT_LIGHT, alignment=TA_CENTER)
        _iav = ParagraphStyle('iav2', fontSize=9,   fontName='Helvetica-Bold',
                               textColor=TEXT_DARK,  alignment=TA_CENTER)

        def _eod_cell(sym):
            d = eod_index.get(sym, {})
            op   = d.get('open',  'N/A')
            hi   = d.get('high',  'N/A')
            lo   = d.get('low',   'N/A')
            cl   = d.get('close', 'N/A')
            chg  = round((cl - op) / op * 100, 2) if isinstance(cl, float) and isinstance(op, float) and op else None
            chg_str   = f'{chg:+.2f}%' if chg is not None else '—'
            chg_color = GREEN.hexval() if (chg or 0) >= 0 else RED.hexval()
            return [
                Paragraph(sym, _ial),
                Paragraph(f'O ${op}', ParagraphStyle('ie1', fontSize=7.5, fontName='Helvetica',
                                                      textColor=TEXT_DARK, alignment=TA_CENTER)),
                Paragraph(f'H ${hi}', ParagraphStyle('ie2', fontSize=7.5, fontName='Helvetica',
                                                      textColor=GREEN, alignment=TA_CENTER)),
                Paragraph(f'L ${lo}', ParagraphStyle('ie3', fontSize=7.5, fontName='Helvetica',
                                                      textColor=RED,   alignment=TA_CENTER)),
                Paragraph(f'C ${cl}', _iav),
                Paragraph(f'<font color="{chg_color}">{chg_str}</font>',
                          ParagraphStyle('ie4', fontSize=8, fontName='Helvetica-Bold',
                                         alignment=TA_CENTER)),
            ]

        idx_syms2 = [s2 for s2 in ['QQQ', 'SPY'] if s2 in eod_index]
        if idx_syms2:
            eod_rows = [[item for sym in idx_syms2 for item in _eod_cell(sym)]]
            eod_col_w = [0.45*inch, 0.75*inch, 0.75*inch, 0.75*inch, 0.75*inch, 0.65*inch] * len(idx_syms2)
            eod_tbl = Table(eod_rows, colWidths=eod_col_w)
            n_cols_per = 6
            eod_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (n_cols_per - 1, 0), colors.HexColor('#EAF5FB')),
                ('BACKGROUND', (n_cols_per, 0), (-1, 0),    BG_LIGHT),
                ('LINEAFTER',  (n_cols_per - 1, 0), (n_cols_per - 1, 0), 1.5, BORDER),
                ('BOX',        (0, 0), (-1, -1), 1, BORDER),
                ('INNERGRID',  (0, 0), (-1, -1), 0.3, BORDER),
                ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING',    (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LEFTPADDING',   (0, 0), (-1, -1), 2),
                ('RIGHTPADDING',  (0, 0), (-1, -1), 2),
            ]))
            story.append(eod_tbl)
            story.append(Spacer(1, 4))

    # ── Trade reviews ──────────────────────────────────────────────────────
    col_w2 = [0.55, 0.45, 0.60, 0.60, 0.60, 0.60, 0.70, 0.75, 1.65, 1.65, 1.75]
    col_w2 = [x * inch for x in col_w2]

    th2 = ParagraphStyle('th2', fontSize=7, textColor=TEXT_WHITE,
                         fontName='Helvetica-Bold', alignment=TA_CENTER)

    header2 = [
        Paragraph('TICKER',      th2),
        Paragraph('DIR',         th2),
        Paragraph('OPEN',        th2),
        Paragraph('HIGH',        th2),
        Paragraph('LOW',         th2),
        Paragraph('CLOSE',       th2),
        Paragraph('OUTCOME',     th2),
        Paragraph('TRIGGERED',   th2),
        Paragraph('WHAT WORKED', th2),
        Paragraph('WHAT FAILED', th2),
        Paragraph('LESSON',      th2),
    ]

    rows2 = [header2]
    c7 = ParagraphStyle('c7', fontSize=7, fontName='Helvetica',
                        textColor=TEXT_DARK, alignment=TA_CENTER)

    for tr in review.get('trade_reviews', []):
        outcome   = tr.get('outcome', 'N/A')
        triggered = tr.get('if_then_triggered', False)

        out_color  = GREEN if outcome == 'Winner' else (RED if outcome == 'Loser' else GOLD)
        trig_color = GREEN if triggered else TEXT_LIGHT

        rows2.append([
            Paragraph(f'<b>{tr.get("ticker","")}</b>',
                      ParagraphStyle('tk3', fontSize=8, fontName='Helvetica-Bold',
                                     textColor=TEXT_DARK, alignment=TA_CENTER)),
            Paragraph(tr.get('predicted_direction', ''), c7),
            Paragraph(f'${tr.get("actual_open","N/A")}',  c7),
            Paragraph(f'${tr.get("actual_high","N/A")}',  c7),
            Paragraph(f'${tr.get("actual_low","N/A")}',   c7),
            Paragraph(f'${tr.get("actual_close","N/A")}', c7),
            Paragraph(outcome,
                      ParagraphStyle('oc', fontSize=8, fontName='Helvetica-Bold',
                                     textColor=out_color, alignment=TA_CENTER)),
            Paragraph('YES' if triggered else 'NO',
                      ParagraphStyle('tr2', fontSize=8, fontName='Helvetica-Bold',
                                     textColor=trig_color, alignment=TA_CENTER)),
            Paragraph(tr.get('what_worked', ''),
                      ParagraphStyle('ww', fontSize=7, fontName='Helvetica',
                                     textColor=GREEN, leading=10)),
            Paragraph(tr.get('what_failed', ''),
                      ParagraphStyle('wf', fontSize=7, fontName='Helvetica',
                                     textColor=RED, leading=10)),
            Paragraph(tr.get('lesson', ''),
                      ParagraphStyle('ls', fontSize=7, fontName='Helvetica',
                                     textColor=GOLD, leading=10)),
        ])

    tbl2 = Table(rows2, colWidths=col_w2, repeatRows=1)
    tbl2.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0),  (-1, 0),  BG_HEADER),
        ('ALIGN',         (0, 0),  (-1, -1), 'CENTER'),
        ('VALIGN',        (0, 0),  (-1, -1), 'TOP'),
        ('BOX',           (0, 0),  (-1, -1), 1, BORDER),
        ('INNERGRID',     (0, 0),  (-1, -1), 0.4, BORDER),
        ('ROWBACKGROUNDS',(0, 1),  (-1, -1), [BG_WHITE, BG_LIGHT]),
        ('LEFTPADDING',   (0, 0),  (-1, -1), 3),
        ('RIGHTPADDING',  (0, 0),  (-1, -1), 3),
        ('TOPPADDING',    (0, 0),  (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0),  (-1, -1), 3),
    ]))
    story.append(tbl2)

    # ── Earnings calendar ──────────────────────────────────────────────────
    earnings = review.get('earnings_calendar', {})
    if earnings:
        story.append(Spacer(1, 8))
        story.append(Paragraph('UPCOMING EARNINGS — Next 5 Trading Days', s['section']))
        story.append(HRFlowable(width='100%', thickness=0.5, color=GOLD, spaceAfter=3))

        earn_h  = [Paragraph(x, ParagraphStyle('eh', fontSize=7, textColor=TEXT_WHITE,
                                                fontName='Helvetica-Bold', alignment=TA_CENTER))
                   for x in ['TICKER', 'EARNINGS DATE', 'DAYS AWAY', 'NOTE']]
        earn_rows = [earn_h]
        for tkr, info in earnings.items():
            days = info.get('days_away', '?')
            warn = 'TODAY' if days == 0 else ('TOMORROW' if days == 1 else f'In {days} days')
            warn_color = RED if days <= 1 else (ORANGE if days <= 2 else GOLD)
            earn_rows.append([
                Paragraph(f'<b>{tkr}</b>',
                          ParagraphStyle('etk', fontSize=8, fontName='Helvetica-Bold',
                                         textColor=TEXT_DARK, alignment=TA_CENTER)),
                Paragraph(info.get('date', '?'),
                          ParagraphStyle('ed', fontSize=8, fontName='Helvetica',
                                         textColor=TEXT_DARK, alignment=TA_CENTER)),
                Paragraph(str(days),
                          ParagraphStyle('eda', fontSize=8, fontName='Helvetica-Bold',
                                         textColor=warn_color, alignment=TA_CENTER)),
                Paragraph(warn,
                          ParagraphStyle('ew', fontSize=8, fontName='Helvetica-Bold',
                                         textColor=warn_color, alignment=TA_CENTER)),
            ])

        earn_tbl = Table(earn_rows, colWidths=[1.0*inch, 1.2*inch, 1.0*inch, 1.5*inch])
        earn_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  BG_HEADER),
            ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX',           (0, 0), (-1, -1), 1, BORDER),
            ('INNERGRID',     (0, 0), (-1, -1), 0.4, BORDER),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [BG_WHITE, BG_LIGHT]),
            ('LEFTPADDING',   (0, 0), (-1, -1), 4),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('TOPPADDING',    (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(earn_tbl)
        story.append(Paragraph(
            '⚠  Tickers with earnings within 2 days carry elevated gap risk — adjust position size accordingly.',
            ParagraphStyle('ewarn', fontSize=7.5, textColor=ORANGE,
                           fontName='Helvetica-Bold', spaceAfter=4)
        ))

    # ── Improvements ───────────────────────────────────────────────────────
    improvements = review.get('suggested_improvements', [])
    if improvements:
        story.append(Spacer(1, 8))
        story.append(Paragraph('SUGGESTED RULE IMPROVEMENTS  —  Pending Your Approval', s['section']))
        story.append(HRFlowable(width='100%', thickness=0.5, color=BLUE, spaceAfter=3))

        imp_w = [1.0 * inch, 2.5 * inch, 2.5 * inch, 3.7 * inch]
        imp_h = [Paragraph(x, ParagraphStyle('imph', fontSize=7, textColor=TEXT_WHITE,
                                              fontName='Helvetica-Bold', alignment=TA_CENTER))
                 for x in ['AREA', 'CURRENT RULE', 'PROPOSED CHANGE', 'REASON']]
        imp_rows = [imp_h]

        for imp in improvements:
            imp_rows.append([
                Paragraph(imp.get('area', ''),
                          ParagraphStyle('ia', fontSize=7, textColor=GOLD,
                                         fontName='Helvetica-Bold', alignment=TA_CENTER)),
                Paragraph(imp.get('current_rule', ''),
                          ParagraphStyle('ic', fontSize=7, textColor=TEXT_MED,
                                         fontName='Helvetica', leading=10)),
                Paragraph(imp.get('proposed_change', ''),
                          ParagraphStyle('ip', fontSize=7, textColor=GREEN,
                                         fontName='Helvetica', leading=10)),
                Paragraph(imp.get('reason', ''),
                          ParagraphStyle('ir', fontSize=7, textColor=TEXT_DARK,
                                         fontName='Helvetica', leading=10)),
            ])

        imp_tbl = Table(imp_rows, colWidths=imp_w, repeatRows=1)
        imp_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  BG_HEADER),
            ('ALIGN',         (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('BOX',           (0, 0), (-1, -1), 1, BORDER),
            ('INNERGRID',     (0, 0), (-1, -1), 0.4, BORDER),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [BG_WHITE, BG_LIGHT]),
            ('LEFTPADDING',   (0, 0), (-1, -1), 4),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('TOPPADDING',    (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(imp_tbl)
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            '⚠  Review each improvement above and reply APPROVE or DENY before any rule changes take effect.',
            ParagraphStyle('warn', fontSize=8, textColor=ORANGE,
                           fontName='Helvetica-Bold', alignment=TA_CENTER)
        ))

    story.append(Spacer(1, 4))
    story.append(HRFlowable(width='100%', thickness=0.5, color=BORDER))
    story.append(Paragraph(
        f'Generated {today} after market close  |  Not financial advice.',
        ParagraphStyle('ft2', fontSize=6, textColor=TEXT_LIGHT,
                       fontName='Helvetica', alignment=TA_CENTER)
    ))

    doc.build(story, canvasmaker=_PageBackground)
    return output_path


# ── Chart page (page 2 of morning report) ─────────────────────────────────

def _generate_chart_image(trade: dict, path: str, figsize=(4.8, 2.6)) -> bool:
    try:
        import yfinance as yf
        import mplfinance as mpf
        import matplotlib.pyplot as plt
        import matplotlib.lines as mlines

        ticker = trade['ticker']
        t      = yf.Ticker(ticker)
        hist   = t.history(period='35d')
        if hist.empty or len(hist) < 5:
            return False

        hist.index = hist.index.tz_localize(None)
        support    = float(trade.get('support',    hist['Low'].min()))
        resistance = float(trade.get('resistance', hist['High'].max()))
        ma20       = hist['Close'].rolling(min(20, len(hist))).mean()

        mc = mpf.make_marketcolors(
            up='#1A7F37', down='#CF222E',
            edge={'up': '#1A7F37', 'down': '#CF222E'},
            wick={'up': '#1A7F37', 'down': '#CF222E'},
            volume={'up': '#A8D5B5', 'down': '#F5B8BB'},
        )
        style = mpf.make_mpf_style(
            marketcolors=mc, facecolor='#FAFBFC',
            gridcolor='#E8ECEF', gridstyle='--', gridaxis='both',
            y_on_right=False,
            rc={'font.size': 7, 'xtick.labelsize': 6, 'ytick.labelsize': 6,
                'axes.spines.top': False, 'axes.spines.right': False}
        )

        fig, axes = mpf.plot(
            hist, type='candle', style=style, volume=True,
            addplot=[mpf.make_addplot(ma20, color='#0969DA', width=1.2)],
            figsize=figsize, panel_ratios=(3, 1), returnfig=True,
            tight_layout=True, warn_too_much_data=9999,
        )

        ax   = axes[0]
        xpos = ax.get_xlim()[0] + (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.01
        ax.axhline(support,    color='#1A7F37', lw=0.9, linestyle='--', alpha=0.85)
        ax.axhline(resistance, color='#CF222E', lw=0.9, linestyle='--', alpha=0.85)
        ax.text(xpos, support,    f'S ${support}',    color='#1A7F37', fontsize=5.5, va='bottom', fontweight='bold')
        ax.text(xpos, resistance, f'R ${resistance}', color='#CF222E', fontsize=5.5, va='top',    fontweight='bold')
        ax.set_title(f'{ticker}  [{trade.get("type","Long")}]', fontsize=8,
                     fontweight='bold', color='#1A1A2E', pad=2, loc='left')
        ax.legend(
            handles=[
                mlines.Line2D([], [], color='#1A7F37', linestyle='--', lw=1, label='Support'),
                mlines.Line2D([], [], color='#CF222E', linestyle='--', lw=1, label='Resist'),
                mlines.Line2D([], [], color='#0969DA', lw=1.2,              label='MA20'),
            ],
            loc='upper right', fontsize=5.5, framealpha=0.75,
            handlelength=1.5, borderpad=0.4, labelspacing=0.3,
        )
        fig.savefig(path, dpi=130, bbox_inches='tight', facecolor='#FAFBFC', edgecolor='none')
        plt.close(fig)
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f'Chart failed {trade.get("ticker")}: {e}')
        return False


def build_charts_page(analysis: dict, chart_dir: str) -> list:
    """Returns flowables for the charts page. Append after PageBreak."""
    os.makedirs(chart_dir, exist_ok=True)
    trades = analysis.get('trades', [])[:10]
    today  = analysis.get('date', date.today().strftime('%Y-%m-%d'))

    PAGE_W   = 11 * inch
    MARGIN_H = 0.28 * inch
    USABLE_W = PAGE_W - MARGIN_H * 2
    COLS     = 4
    COL_W    = USABLE_W / COLS
    CHART_W  = COL_W - 0.10 * inch
    CHART_H  = 1.50 * inch   # reduced to give more room to if/then text
    HDR_H    = 0.26 * inch
    IFTHEN_H = 0.58 * inch   # increased so text is fully readable

    CONV_C = {'High': '#1A7F37', 'Medium': '#9A6700', 'Low': '#CF222E'}
    tk_s = ParagraphStyle('ctk', fontSize=9,   fontName='Helvetica-Bold',
                           textColor=TEXT_DARK,  alignment=TA_CENTER)
    sm_s = ParagraphStyle('csm', fontSize=6.5, fontName='Helvetica',
                           textColor=TEXT_LIGHT, alignment=TA_CENTER, leading=9)
    it_s = ParagraphStyle('cit', fontSize=7,   fontName='Helvetica',
                           textColor=TEXT_DARK,  leading=10, alignment=TA_CENTER)
    na_s = ParagraphStyle('cna', fontSize=7,   fontName='Helvetica',
                           textColor=TEXT_LIGHT, alignment=TA_CENTER)

    chart_paths = {}
    for trade in trades:
        p = os.path.join(chart_dir, f'{trade["ticker"]}.png')
        if _generate_chart_image(trade, p):
            chart_paths[trade['ticker']] = p

    def _hdr(trade):
        dc  = '#1A7F37' if trade.get('type') == 'Long' else '#CF222E'
        cc  = CONV_C.get(trade.get('conviction', 'Medium'), '#444444')
        gap = f'  Gap {trade["pre_gap"]:+.1f}%' if trade.get('pre_gap') is not None else ''
        inner = Table(
            [[Paragraph(f'<b>{trade["ticker"]}</b>', tk_s)],
             [Paragraph(f'<font color="{dc}"><b>{trade.get("type","Long")}</b></font>'
                        f'  <font color="{cc}">{trade.get("conviction","")}</font>'
                        f'  ${trade.get("price","")}{gap}', sm_s)]],
            colWidths=[COL_W]
        )
        inner.setStyle(TableStyle([
            ('BACKGROUND',   (0,0),(-1,-1), BG_LIGHT),
            ('ALIGN',        (0,0),(-1,-1), 'CENTER'),
            ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
            ('LEFTPADDING',  (0,0),(-1,-1), 2),
            ('RIGHTPADDING', (0,0),(-1,-1), 2),
            ('TOPPADDING',   (0,0),(-1,-1), 1),
            ('BOTTOMPADDING',(0,0),(-1,-1), 1),
        ]))
        return inner

    empty  = Paragraph('', na_s)
    groups = [trades[0:4], trades[4:8], trades[8:10]]
    rows, row_h = [], []

    for group in groups:
        pad = COLS - len(group)
        rows.append([_hdr(t) for t in group] + [empty] * pad)
        row_h.append(HDR_H)
        rows.append([
            Image(chart_paths[t['ticker']], width=CHART_W, height=CHART_H)
            if t['ticker'] in chart_paths else Paragraph('No data', na_s)
            for t in group
        ] + [empty] * pad)
        row_h.append(CHART_H + 0.05 * inch)
        rows.append([Paragraph(t.get('if_then', ''), it_s) for t in group] + [empty] * pad)
        row_h.append(IFTHEN_H)

    tbl = Table(rows, colWidths=[COL_W] * COLS, rowHeights=row_h)
    tbl.setStyle(TableStyle([
        ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('BOX',           (0,0),(-1,-1), 1,   BORDER),
        ('INNERGRID',     (0,0),(-1,-1), 0.5, BORDER),
        ('BACKGROUND',    (0,0),(-1,-1), BG_WHITE),
        ('LEFTPADDING',   (0,0),(-1,-1), 3),
        ('RIGHTPADDING',  (0,0),(-1,-1), 3),
        ('TOPPADDING',    (0,0),(-1,-1), 2),
        ('BOTTOMPADDING', (0,0),(-1,-1), 2),
    ]))

    return [
        Paragraph(f'TRADE SETUPS  ·  30-DAY CHARTS  ·  {today}',
                  ParagraphStyle('cpgt', fontSize=12, fontName='Helvetica-Bold',
                                 textColor=TEXT_WHITE, alignment=TA_CENTER)),
        Paragraph('Green dashed = Support  ·  Red dashed = Resistance  ·  Blue = MA20  ·  Volume bars below',
                  ParagraphStyle('cpgs', fontSize=7, fontName='Helvetica',
                                 textColor=TEXT_WHITE, alignment=TA_CENTER, spaceAfter=5)),
        tbl,
        Spacer(1, 3),
        HRFlowable(width='100%', thickness=0.5, color=BORDER),
        Paragraph('Charts show last 30 trading days. Not financial advice.',
                  ParagraphStyle('cpgf', fontSize=6, fontName='Helvetica',
                                 textColor=TEXT_LIGHT, alignment=TA_CENTER)),
    ]
