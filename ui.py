"""Shared look for the dashboard pages: Apple-style cards, rings, grouped lists and a Plotly theme.

Colors by role (never by rank): complete = status good, running = blue, queued = neutral gray,
stopped = status serious, failed = status critical, not started = track gray. Every color is
paired with a text label, so nothing is read from color alone.
"""
import html

import streamlit as st

FONT = ('-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Inter", '
        '"Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif')

INK = "#1d1d1f"         # primary text
INK_2 = "#6e6e73"       # secondary text
INK_3 = "#86868b"       # muted text
TRACK = "#e8e8ed"       # empty ring / bar track
GRID = "#ececf0"        # chart grid
SURFACE = "#ffffff"     # card
PAGE = "#f5f5f7"        # page background
ACCENT = "#0071e3"      # links, selected controls

COLORS = {
    "complete": "#0ca30c",
    "running": "#2a78d6",
    "queued": "#a1a1a6",
    "stopped": "#ec835a",
    "failed": "#d03b3b",
    "remaining": TRACK,
}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]   # categorical slots 1-3 (validated all-pairs)

CSS = f"""
<style>
.stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp h1, .stApp h2, .stApp h3,
.stApp [data-testid="stMetricValue"], .stApp [data-testid="stMetricLabel"] div,
.stApp [data-baseweb="select"] div {{ font-family: {FONT} !important; }}
/* icons are spans with their own icon font: never matched above */
.stApp {{ background: {PAGE}; }}
.block-container {{ max-width: 1180px; padding-top: 2.2rem; padding-bottom: 4rem; }}
h1, h2, h3 {{ letter-spacing: -0.02em; color: {INK}; }}
[data-testid="stSidebar"] {{ background: #fbfbfd; border-right: 1px solid #e5e5ea; }}
[data-testid="stHeader"] {{ background: transparent; }}
hr {{ display: none; }}
.lwi-head {{ display: flex; align-items: flex-end; justify-content: space-between; gap: 16px;
  flex-wrap: wrap; margin: 0 0 18px; }}
.lwi-eyebrow {{ font-size: 13px; font-weight: 600; color: {INK_3}; text-transform: uppercase;
  letter-spacing: .06em; margin: 0 0 4px; }}
.lwi-title {{ font-size: 40px; line-height: 1.05; font-weight: 700; letter-spacing: -0.03em;
  color: {INK}; margin: 0; }}
.lwi-sub {{ font-size: 17px; color: {INK_2}; margin: 6px 0 0; }}
.lwi-pill {{ display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 999px;
  background: {SURFACE}; color: {INK_2}; font-size: 13px; font-weight: 500;
  box-shadow: 0 1px 2px rgba(0,0,0,.06); white-space: nowrap; }}
.lwi-dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex: none; }}
.lwi-card {{ background: {SURFACE}; border-radius: 20px; padding: 22px 24px;
  box-shadow: 0 1px 2px rgba(0,0,0,.04), 0 6px 24px rgba(0,0,0,.05); margin-bottom: 16px; }}
.lwi-section {{ font-size: 22px; font-weight: 700; letter-spacing: -0.02em; color: {INK};
  margin: 26px 0 12px; }}
.lwi-section small {{ font-size: 15px; font-weight: 500; color: {INK_3}; margin-left: 8px; letter-spacing: 0; }}
.lwi-hero {{ display: flex; align-items: center; gap: 36px; flex-wrap: wrap; }}
.lwi-kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 22px 28px; flex: 1;
  min-width: 280px; }}
.lwi-kpi-label {{ font-size: 13px; font-weight: 600; color: {INK_3}; display: flex; align-items: center; gap: 7px; }}
.lwi-kpi-value {{ font-size: 34px; font-weight: 700; letter-spacing: -0.025em; color: {INK};
  font-variant-numeric: tabular-nums; line-height: 1.15; margin-top: 2px; }}
.lwi-kpi-note {{ font-size: 13px; color: {INK_2}; margin-top: 1px; }}
.lwi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }}
.lwi-region {{ display: flex; align-items: center; gap: 18px; margin: 0; }}
.lwi-region-name {{ font-size: 17px; font-weight: 600; color: {INK}; }}
.lwi-region-num {{ font-size: 15px; color: {INK_2}; font-variant-numeric: tabular-nums; margin-top: 2px; }}
.lwi-chips {{ display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }}
.lwi-chip {{ display: inline-flex; align-items: center; gap: 5px; font-size: 12px; font-weight: 600;
  padding: 3px 9px; border-radius: 999px; background: #f2f2f7; color: {INK_2}; }}
.lwi-list {{ background: {SURFACE}; border-radius: 16px; overflow: hidden; margin-bottom: 16px;
  box-shadow: 0 1px 2px rgba(0,0,0,.04), 0 6px 24px rgba(0,0,0,.05); }}
.lwi-list-head {{ font-size: 13px; font-weight: 600; color: {INK_3}; text-transform: uppercase;
  letter-spacing: .05em; padding: 14px 20px 6px; }}
.lwi-row {{ display: grid; grid-template-columns: minmax(0, 1fr) 110px 110px; align-items: center; gap: 12px;
  padding: 12px 20px; border-top: 1px solid #ededf0; }}
.lwi-row:first-of-type {{ border-top: none; }}
.lwi-row-name {{ font-size: 15px; font-weight: 600; color: {INK}; }}
.lwi-row-sub {{ font-size: 13px; color: {INK_2}; margin-top: 2px; }}
.lwi-row-num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.lwi-row-num b {{ display: block; font-size: 17px; color: {INK}; }}
.lwi-row-num span {{ font-size: 12px; color: {INK_3}; }}
.lwi-bar {{ display: flex; height: 10px; border-radius: 999px; overflow: hidden; background: {TRACK}; gap: 2px; }}
.lwi-legend {{ display: flex; gap: 16px; flex-wrap: wrap; margin-top: 10px; font-size: 13px; color: {INK_2}; }}
.lwi-legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; background: #e9e9ee; padding: 4px; border-radius: 12px;
  width: fit-content; max-width: 100%; overflow-x: auto; }}
.stTabs [data-baseweb="tab"] {{ height: 34px; padding: 0 16px; border-radius: 9px; font-weight: 600;
  font-size: 14px; color: {INK_2}; background: transparent; }}
.stTabs [aria-selected="true"] {{ background: {SURFACE} !important; color: {INK} !important;
  box-shadow: 0 1px 3px rgba(0,0,0,.12); }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none; }}
[data-testid="stPlotlyChart"], [data-testid="stDataFrame"] {{ background: {SURFACE}; border-radius: 16px;
  padding: 10px 12px; box-shadow: 0 1px 2px rgba(0,0,0,.04), 0 6px 24px rgba(0,0,0,.05); }}
@media (max-width: 640px) {{
  .lwi-title {{ font-size: 30px; }}
  .lwi-kpi-value {{ font-size: 28px; }}
  .lwi-row {{ grid-template-columns: minmax(0, 1fr) 80px 80px; padding: 12px 14px; }}
}}
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)


def esc(x):
    return html.escape(str(x))


def raw(markup):
    """Render HTML. Joined on one line: indented lines would turn into Markdown code blocks."""
    st.markdown(" ".join(line.strip() for line in markup.splitlines()), unsafe_allow_html=True)


def dot(color):
    return f'<span class="lwi-dot" style="background:{color}"></span>'


def header(eyebrow, title, subtitle="", pill=""):
    raw(f'<div class="lwi-head"><div><p class="lwi-eyebrow">{esc(eyebrow)}</p>'
        f'<h1 class="lwi-title">{esc(title)}</h1>'
        + (f'<p class="lwi-sub">{esc(subtitle)}</p>' if subtitle else "")
        + "</div>" + (f'<span class="lwi-pill">{pill}</span>' if pill else "") + "</div>")


def section(title, note=""):
    raw(f'<div class="lwi-section">{esc(title)}' + (f"<small>{esc(note)}</small>" if note else "") + "</div>")


def ring(parts, total, size=150, width=16, center="", sub=""):
    """Activity-style ring. parts: [(value, color)] drawn clockwise from 12 o'clock on a gray track."""
    r = (size - width) / 2
    c = 2 * 3.141592653589793 * r
    arcs, start = [], 0.0
    for value, color in parts:
        frac = max(0.0, min(value / total, 1.0 - start)) if total else 0.0
        if frac > 0:
            arcs.append(f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="{color}" '
                        f'stroke-width="{width}" stroke-linecap="round" '
                        f'stroke-dasharray="{max(frac * c - 2, 0.1):.2f} {c:.2f}" '
                        f'stroke-dashoffset="{-start * c:.2f}" '
                        f'transform="rotate(-90 {size/2} {size/2})"/>')
            start += frac
    fs = size * 0.2
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" '
            f'aria-label="{esc(center)} {esc(sub)}" style="flex:none">'
            f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="{TRACK}" stroke-width="{width}"/>'
            + "".join(arcs)
            + f'<text x="50%" y="{size/2 + (0 if sub else fs*0.35):.1f}" text-anchor="middle" '
              f'font-family=\'{FONT}\' font-size="{fs:.0f}" font-weight="700" fill="{INK}">{esc(center)}</text>'
            + (f'<text x="50%" y="{size/2 + fs*0.95:.1f}" text-anchor="middle" font-family=\'{FONT}\' '
               f'font-size="{size*0.085:.0f}" font-weight="500" fill="{INK_3}">{esc(sub)}</text>' if sub else "")
            + "</svg>")


def kpi(label, value, note="", color=None):
    return (f'<div><div class="lwi-kpi-label">{dot(color) if color else ""}{esc(label)}</div>'
            f'<div class="lwi-kpi-value">{esc(value)}</div>'
            + (f'<div class="lwi-kpi-note">{esc(note)}</div>' if note else "") + "</div>")


def chip(text, color=None):
    return f'<span class="lwi-chip">{dot(color) if color else ""}{esc(text)}</span>'


def stacked_bar(parts, total):
    """Thin segmented bar: parts = [(value, color, label)]; the gray track is what is left."""
    segs = "".join(f'<div style="width:{100 * v / total:.3f}%;background:{c}" title="{esc(l)}: {v:,}"></div>'
                   for v, c, l in parts if total and v > 0)
    legend = "".join(f"<span>{dot(c)}{esc(l)} <b>{v:,}</b></span>" for v, c, l in parts)
    return f'<div class="lwi-bar">{segs}</div><div class="lwi-legend">{legend}</div>'


def grouped_list(title, rows):
    """iOS-style inset grouped list. rows: [(name, sub, (num, label), (num, label))]."""
    body = "".join(
        f'<div class="lwi-row"><div><div class="lwi-row-name">{esc(n)}</div>'
        + (f'<div class="lwi-row-sub">{esc(s)}</div>' if s else "") + "</div>"
        + "".join(f'<div class="lwi-row-num"><b>{esc(v)}</b><span>{esc(l)}</span></div>' for v, l in (a, b))
        + "</div>"
        for n, s, a, b in rows)
    return f'<div class="lwi-list"><div class="lwi-list-head">{esc(title)}</div>{body}</div>'


def style_fig(fig, height=340, title=None, ytitle=None, xtitle=None):
    """Quiet Plotly theme: system font, recessive grid, no chart junk, readable hover."""
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=48 if title else 16, b=8),
        title=dict(text=title, x=0, xanchor="left", font=dict(size=17, color=INK)) if title else None,
        font=dict(family=FONT, size=13, color=INK_2),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor=SURFACE, bordercolor="#d2d2d7", font=dict(family=FONT, size=13, color=INK)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1, title=None,
                    font=dict(size=12)),
        bargap=0.25,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="#d2d2d7", ticks="", title=xtitle)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, showline=False, ticks="", title=ytitle)
    return fig


PLOT_CONFIG = {"displaylogo": False, "responsive": True,
               "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}
