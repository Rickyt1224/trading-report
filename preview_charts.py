import json, sys, os
sys.path.insert(0, 'src')

import yfinance as yf
import mplfinance as mpf
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Image, Table, TableStyle,
    Paragraph, Spacer, HRFlowable
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfgen.canvas import Canvas

os.makedirs('data/charts', exist_ok=True)

with open('data/2026-05-31_morning_analysis.json') as f:
    data = json.load(f)

trades = data['analysis']['trades'][:10]

# ── candlestick style ──────────────────────────────────────────────────────
mc = mpf.make_marketcolors(
    up='#1A7F37', down='#CF222E',
    edge={'up': '#1A7F37', 'down': '#CF222E'},
    wick={'up': '#1A7F37', 'down': '#CF222E'},
    volume={'up': '#A8D5B5', 'down': '#F5B8BB'},
)
style = mpf.make_mpf_style(
    marketcolors=mc,
    facecolor='#FAFBFC',
    gridcolor='#E8ECEF',
    gridstyle='--',
    gridaxis='both',
    y_on_right=False,
    rc={
        'font.size': 7,
        'axes.labelsize': 7,
        'xtick.labelsize': 6,
        'ytick.labelsize': 6,
        'axes.spines.top': False,
        'axes.spines.right': False,
    }
)

chart_paths = {}

for trade in trades:
    ticker = trade['ticker']
    try:
        t    = yf.Ticker(ticker)
        hist = t.history(period='35d')
        if hist.empty or len(hist) < 5:
            continue

        hist.index = hist.index.tz_localize(None)
        support    = trade.get('support',    float(hist['Low'].min()))
        resistance = trade.get('resistance', float(hist['High'].max()))
        ma20       = hist['Close'].rolling(min(20, len(hist))).mean()

        add_plots = [
            mpf.make_addplot(ma20, color='#0969DA', width=1.2),
        ]

        fig, axes = mpf.plot(
            hist,
            type='candle',
            style=style,
            volume=True,
            addplot=add_plots,
            figsize=(4.2, 2.4),
            panel_ratios=(3, 1),
            returnfig=True,
            tight_layout=True,
            warn_too_much_data=9999,
        )

        ax = axes[0]
        ax.axhline(support,    color='#1A7F37', linewidth=0.9, linestyle='--', alpha=0.85)
        ax.axhline(resistance, color='#CF222E', linewidth=0.9, linestyle='--', alpha=0.85)

        xlim = ax.get_xlim()
        xpos = xlim[0] + (xlim[1] - xlim[0]) * 0.01
        ax.text(xpos, support,    f'S ${support}',    color='#1A7F37',
                fontsize=5.5, va='bottom', fontweight='bold')
        ax.text(xpos, resistance, f'R ${resistance}', color='#CF222E',
                fontsize=5.5, va='top',    fontweight='bold')

        direction = trade.get('type', 'Long')
        ax.set_title(f'{ticker}  [{direction}]', fontsize=8, fontweight='bold',
                     color='#1A1A2E', pad=3, loc='left')

        s_line  = mlines.Line2D([], [], color='#1A7F37', linestyle='--', lw=1,  label=f'Support')
        r_line  = mlines.Line2D([], [], color='#CF222E', linestyle='--', lw=1,  label=f'Resist')
        ma_line = mlines.Line2D([], [], color='#0969DA', lw=1.2,                label='MA20')
        ax.legend(handles=[s_line, r_line, ma_line],
                  loc='upper right', fontsize=5.5, framealpha=0.75,
                  handlelength=1.5, borderpad=0.4, labelspacing=0.3)

        path = f'data/charts/{ticker}.png'
        fig.savefig(path, dpi=140, bbox_inches='tight',
                    facecolor='#FAFBFC', edgecolor='none')
        plt.close(fig)
        chart_paths[ticker] = path
        print(f'  Chart saved: {ticker}')
    except Exception as e:
        print(f'  SKIP {ticker}: {e}')

# ── colours ────────────────────────────────────────────────────────────────
BG_TITLE  = colors.HexColor('#0D1117')
BG_HEADER = colors.HexColor('#1C2128')
BG_LIGHT  = colors.HexColor('#F6F8FA')
TEXT_WHITE = colors.white
TEXT_DARK  = colors.HexColor('#1A1A2E')
TEXT_LIGHT = colors.HexColor('#666666')
BORDER     = colors.HexColor('#D0D7DE')
C_GREEN    = colors.HexColor('#1A7F37')
C_RED      = colors.HexColor('#CF222E')
C_GOLD     = colors.HexColor('#9A6700')


class _TitleBand(Canvas):
    BAND = 0.55 * inch
    def showPage(self):
        w, h = self._pagesize
        self.saveState()
        self.setFillColor(BG_TITLE)
        self.rect(0, h - self.BAND, w, self.BAND, fill=1, stroke=0)
        self.restoreState()
        super().showPage()


# ── page uses full landscape letter with tighter margins ──────────────────
PAGE_W, PAGE_H = landscape(letter)   # 11 x 8.5 inches
MARGIN_H = 0.30 * inch
MARGIN_V_TOP = 0.62 * inch
MARGIN_V_BOT = 0.20 * inch

# 4 columns, 3 rows of charts  →  layout: [4] [4] [2]
COLS        = 4
USABLE_W    = PAGE_W - MARGIN_H * 2
COL_W       = USABLE_W / COLS
CHART_W     = COL_W - 0.08 * inch

# Available vertical space after title band + footer
USABLE_H    = PAGE_H - MARGIN_V_TOP - MARGIN_V_BOT - 0.55 * inch  # 0.55 = title band
# Split across 3 row-groups (header + chart + ifthen each)
ROW_GROUP_H = USABLE_H / 3
HDR_H       = 0.30 * inch
IFTHEN_H    = 0.38 * inch
CHART_H     = ROW_GROUP_H - HDR_H - IFTHEN_H - 0.06 * inch   # slight padding

doc = SimpleDocTemplate(
    'reports/charts_preview_v2.pdf',
    pagesize=landscape(letter),
    leftMargin=MARGIN_H,
    rightMargin=MARGIN_H,
    topMargin=MARGIN_V_TOP,
    bottomMargin=MARGIN_V_BOT,
)

title_s = ParagraphStyle('ts', fontSize=13, fontName='Helvetica-Bold',
                          textColor=TEXT_WHITE, alignment=TA_CENTER)
sub_s   = ParagraphStyle('ss', fontSize=8, fontName='Helvetica',
                          textColor=TEXT_WHITE, alignment=TA_CENTER)
tk_s    = ParagraphStyle('tk', fontSize=9, fontName='Helvetica-Bold',
                          textColor=TEXT_DARK, alignment=TA_CENTER)
sm_s    = ParagraphStyle('sm', fontSize=7, fontName='Helvetica',
                          textColor=TEXT_LIGHT, alignment=TA_CENTER, leading=10)
it_s    = ParagraphStyle('it', fontSize=6.5, fontName='Helvetica',
                          textColor=TEXT_DARK, leading=9, alignment=TA_CENTER)

story = [
    Paragraph('TRADE SETUPS — 30-DAY CHARTS', title_s),
    Paragraph('2026-05-31  ·  Top 10 Picks  ·  Support / Resistance / MA20 marked', sub_s),
    Spacer(1, 5),
]

CONV_COLORS = {'High': '#1A7F37', 'Medium': '#9A6700', 'Low': '#CF222E'}

# Groups: [0-3], [4-7], [8-9]  — pad last group to 4 with empty cells
groups = [trades[0:4], trades[4:8], trades[8:10]]

def make_header_cell(trade, col_w):
    ticker    = trade['ticker']
    direction = trade.get('type', 'Long')
    conv      = trade.get('conviction', 'Medium')
    price     = trade.get('price', '')
    pre_gap   = trade.get('pre_gap')
    dc        = '#1A7F37' if direction == 'Long' else '#CF222E'
    cc        = CONV_COLORS.get(conv, '#444444')
    gap_str   = f'  Gap {pre_gap:+.1f}%' if pre_gap is not None else ''
    cell = [
        Paragraph(f'<b>{ticker}</b>', tk_s),
        Paragraph(
            f'<font color="{dc}"><b>{direction}</b></font>'
            f'  <font color="{cc}">{conv}</font>'
            f'  ${price}{gap_str}',
            sm_s
        ),
    ]
    ht = Table([cell], colWidths=[col_w])
    ht.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,-1), BG_LIGHT),
        ('ALIGN',        (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING',  (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING',   (0,0), (-1,-1), 2),
        ('BOTTOMPADDING',(0,0), (-1,-1), 2),
    ]))
    return ht

rows = []
row_heights = []

for g_idx, group in enumerate(groups):
    n       = len(group)
    # last group may have fewer — give those charts more width
    g_col_w = USABLE_W / n if n < COLS else COL_W
    g_chrt_w= g_col_w - 0.08 * inch

    # re-generate larger charts for last row if needed
    if n < COLS:
        for trade in group:
            ticker = trade['ticker']
            try:
                t    = yf.Ticker(ticker)
                hist = t.history(period='35d')
                if hist.empty: continue
                hist.index = hist.index.tz_localize(None)
                support    = trade.get('support',    float(hist['Low'].min()))
                resistance = trade.get('resistance', float(hist['High'].max()))
                ma20       = hist['Close'].rolling(min(20, len(hist))).mean()
                add_plots  = [mpf.make_addplot(ma20, color='#0969DA', width=1.2)]
                fig, axes  = mpf.plot(hist, type='candle', style=style, volume=True,
                                      addplot=add_plots, figsize=(5.5, 2.8),
                                      panel_ratios=(3,1), returnfig=True,
                                      tight_layout=True, warn_too_much_data=9999)
                ax = axes[0]
                ax.axhline(support,    color='#1A7F37', lw=0.9, linestyle='--', alpha=0.85)
                ax.axhline(resistance, color='#CF222E', lw=0.9, linestyle='--', alpha=0.85)
                xlim = ax.get_xlim()
                xpos = xlim[0] + (xlim[1]-xlim[0])*0.01
                ax.text(xpos, support,    f'S ${support}',    color='#1A7F37', fontsize=6, va='bottom', fontweight='bold')
                ax.text(xpos, resistance, f'R ${resistance}', color='#CF222E', fontsize=6, va='top',    fontweight='bold')
                direction = trade.get('type','Long')
                ax.set_title(f'{ticker}  [{direction}]', fontsize=9, fontweight='bold', color='#1A1A2E', pad=3, loc='left')
                s_line  = mlines.Line2D([],[],color='#1A7F37',linestyle='--',lw=1,label='Support')
                r_line  = mlines.Line2D([],[],color='#CF222E',linestyle='--',lw=1,label='Resist')
                ma_line = mlines.Line2D([],[],color='#0969DA',lw=1.2,label='MA20')
                ax.legend(handles=[s_line,r_line,ma_line],loc='upper right',fontsize=6,
                          framealpha=0.75,handlelength=1.5,borderpad=0.4,labelspacing=0.3)
                path = f'data/charts/{ticker}_lg.png'
                fig.savefig(path, dpi=140, bbox_inches='tight', facecolor='#FAFBFC', edgecolor='none')
                plt.close(fig)
                chart_paths[ticker] = path
            except Exception as e:
                print(f'  SKIP large {ticker}: {e}')

    # header row
    hdr_row = [make_header_cell(t, g_col_w) for t in group]
    if n < COLS:
        hdr_row += [Paragraph('', sm_s)] * (COLS - n)
    rows.append(hdr_row)
    row_heights.append(HDR_H)

    # chart row
    chart_row = []
    for trade in group:
        ticker = trade['ticker']
        if ticker in chart_paths:
            chart_row.append(Image(chart_paths[ticker], width=g_chrt_w, height=CHART_H))
        else:
            chart_row.append(Paragraph('Chart unavailable', sm_s))
    if n < COLS:
        chart_row += [Paragraph('', sm_s)] * (COLS - n)
    rows.append(chart_row)
    row_heights.append(CHART_H + 0.06 * inch)

    # if/then row
    it_row = [Paragraph(t.get('if_then', ''), it_s) for t in group]
    if n < COLS:
        it_row += [Paragraph('', sm_s)] * (COLS - n)
    rows.append(it_row)
    row_heights.append(IFTHEN_H)

col_widths = [COL_W] * COLS

tbl = Table(rows, colWidths=col_widths, rowHeights=row_heights)
tbl.setStyle(TableStyle([
    ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
    ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
    ('BOX',           (0,0), (-1,-1), 1,   BORDER),
    ('INNERGRID',     (0,0), (-1,-1), 0.5, BORDER),
    ('BACKGROUND',    (0,0), (-1,-1), colors.white),
    ('LEFTPADDING',   (0,0), (-1,-1), 3),
    ('RIGHTPADDING',  (0,0), (-1,-1), 3),
    ('TOPPADDING',    (0,0), (-1,-1), 2),
    ('BOTTOMPADDING', (0,0), (-1,-1), 2),
]))

story.append(tbl)
story.append(Spacer(1, 4))
story.append(HRFlowable(width='100%', thickness=0.5, color=BORDER))
story.append(Paragraph(
    'Candles: green = up day, red = down day  ·  Volume bars below  ·  '
    'Green dashed = Support  ·  Red dashed = Resistance  ·  Blue line = MA20',
    ParagraphStyle('ft', fontSize=6, fontName='Helvetica',
                   textColor=TEXT_LIGHT, alignment=TA_CENTER)
))

doc.build(story, canvasmaker=_TitleBand)
print('Saved: reports/charts_preview_v2.pdf')
