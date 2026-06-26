"""
Equity Research — Streamlit web app
===================================
A free, no-login equity research dashboard: enter a ticker and get valuation
metrics, price action with a moving average, relative performance vs the S&P 500,
risk stats, capital return, a 3-year trailing P/E line, quarterly revenue / profit
and cash flow, plus a peer comparison table and a valuation-vs-momentum bubble map.

Data: Yahoo Finance (via yfinance). For research/education only — not investment advice.
"""

import html as _html
from datetime import datetime

import streamlit as st
import plotly.graph_objects as go

from research_data import build_payload

# ── palette (matches the desktop workbench) ──────────────────────────────────
C = {
    "bg": "#0D1117", "panel": "#161B22", "border": "#30363D",
    "green": "#3FB950", "red": "#F85149", "yellow": "#D29922",
    "blue": "#58A6FF", "purple": "#BC8CFF", "orange": "#FFA657",
    "teal": "#39D353", "sub": "#8B949E", "text": "#E6EDF3",
}

st.set_page_config(page_title="Equity Research", page_icon="📈", layout="wide")

st.markdown("""
<style>
.stApp { background:#0D1117; }
.block-container { padding-top:3rem; padding-bottom:2rem; max-width:1340px; }
section.main h1 { font-size:24px; }
[data-testid="stMetricValue"] { font-size:18px; }
.erh { font-size:13px; font-weight:600; text-transform:uppercase; letter-spacing:.05em;
       color:#E6EDF3; margin:16px 0 8px; }
.erh .sub { color:#8B949E; font-weight:400; text-transform:none; letter-spacing:0; font-size:11px; }
.tilegrid { display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:8px; margin:4px 0 6px; }
.tile { background:#161B22; border:1px solid #30363D; border-radius:8px; padding:8px 12px; }
.tile .lab { font-size:9px; color:#8B949E; text-transform:uppercase; letter-spacing:.06em; }
.tile .val { font-size:18px; font-weight:700; line-height:1.35; }
.tile .nt { font-size:8px; color:#8B949E; margin-top:1px; letter-spacing:.03em; }
.bann { display:flex; justify-content:space-between; align-items:flex-start; gap:16px;
        background:#161B22; border:1px solid #30363D; border-radius:10px; padding:14px 18px; margin-bottom:10px; }
table.rk, table.pt { width:100%; border-collapse:collapse; font-size:12px; }
table.rk { background:#161B22; border:1px solid #30363D; border-radius:8px; overflow:hidden; }
table.rk td { padding:6px 12px; border-bottom:1px solid #21262D; }
table.rk tr:last-child td { border-bottom:none; }
table.rk td.l { color:#8B949E; } table.rk td.r { text-align:right; font-weight:700; }
.ptwrap { background:#161B22; border:1px solid #30363D; border-radius:8px; overflow:hidden; }
table.pt th { color:#8B949E; font-size:9px; text-transform:uppercase; letter-spacing:.05em;
              text-align:right; padding:7px 10px; border-bottom:1px solid #30363D; }
table.pt th.l, table.pt td.l { text-align:left; }
table.pt td { padding:6px 10px; border-bottom:1px solid #21262D; text-align:right; color:#E6EDF3; }
table.pt tr:last-child td { border-bottom:none; }
table.pt tr.tgt td { background:rgba(255,166,87,0.10); }
</style>
""", unsafe_allow_html=True)


# ── formatting helpers ───────────────────────────────────────────────────────
def esc(s):
    return _html.escape(str(s)) if s is not None else ""

def fmt_mc(v):
    if v is None:
        return "—"
    if v >= 1e12:
        return f"${v/1e12:.2f}T"
    if v >= 1e9:
        return f"${v/1e9:.1f}B"
    if v >= 1e6:
        return f"${v/1e6:.0f}M"
    return "—"

def _x(x, suf="×"):
    return f"{x:.1f}{suf}" if x is not None else "—"

def _g(x):
    return (f"+{x:.1f}%" if x >= 0 else f"{x:.1f}%") if x is not None else "—"


def _parse_date(s):
    for fmt in ("%Y-%m-%d", "%b %Y", "%Y-%m"):
        try:
            return datetime.strptime(str(s), fmt)
        except Exception:
            pass
    return None

def _tick(s):
    dt = _parse_date(s)
    return dt.strftime("%b '%y") if dt else str(s)

def _idx_ticks(dates):
    """Plot time series on an integer index (so duplicate/odd date labels can't
    collapse points) and return tick positions labelled with months."""
    n = len(dates)
    xi = list(range(n))
    if n <= 1:
        return xi, xi, [_tick(s) for s in dates]
    tv = sorted(set(int(round(i * (n - 1) / 6)) for i in range(7)))
    tt = [_tick(dates[i]) for i in tv]
    return xi, tv, tt


def _base_layout(fig, height=320, date_axis=False):
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=12, t=24, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=C["bg"],
        font=dict(family="ui-monospace, monospace", size=11, color=C["sub"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
        xaxis=dict(gridcolor=C["border"], zeroline=False, showline=False),
        yaxis=dict(gridcolor=C["border"], zeroline=False),
        hovermode="x unified",
    )
    return fig

_CHART_CFG = {"displayModeBar": False}


@st.cache_data(ttl=900, show_spinner=False)
def load(ticker):
    return build_payload(ticker)


# ── header / input ───────────────────────────────────────────────────────────
st.markdown("## 📈 Equity Research")
st.caption("Free research dashboard — enter a ticker for valuation, price action, cash flow and "
           "peers. Data: Yahoo Finance · for research only, not investment advice.")

col_in, col_btn = st.columns([4, 1])
with col_in:
    ticker = st.text_input("Ticker symbol", value="", placeholder="e.g. AAPL, MSFT, NVDA",
                           label_visibility="collapsed").strip().upper()
with col_btn:
    st.button("Generate report", type="primary", use_container_width=True)

if not ticker:
    st.info("Enter a stock ticker above and press **Generate report**.")
    st.stop()

try:
    with st.spinner(f"Fetching data for {ticker}…"):
        d = load(ticker)
except Exception as e:
    st.error(f"Could not load **{ticker}**. {e}")
    st.stop()

v = d.get("valuation", {}) or {}
r = d.get("risk", {}) or {}

# ── company banner ───────────────────────────────────────────────────────────
st.markdown(f"""
<div class="bann">
  <div>
    <div style="font-size:22px;font-weight:700;color:{C['text']};">{esc(d['company_name'])}
      <span style="color:{C['sub']};font-weight:400;font-size:15px;">{esc(d['ticker'])}</span></div>
    <div style="color:{C['sub']};font-size:12px;margin-top:2px;">{esc(d.get('sector',''))}{(' · ' + esc(d['industry'])) if d.get('industry') else ''}</div>
  </div>
  <div style="text-align:right;">
    <div style="font-size:26px;font-weight:700;color:{C['blue']};">${d['current_price']:.2f}</div>
    <div style="color:{C['sub']};font-size:11px;">Market cap {esc(d['market_cap_str'])}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── valuation tiles ──────────────────────────────────────────────────────────
def _peg_col(x):
    if x is None:
        return C["text"]
    return C["green"] if x < 1.5 else (C["red"] if x > 3 else C["text"])

tiles = [
    ("P/E TTM",  _x(v.get("pe_ttm")),  "trailing 12-mo", C["yellow"]),
    ("Fwd P/E",  _x(v.get("fwd_pe")),  "next-yr estimate", C["yellow"]),
    ("PEG",      f"{v['peg']:.2f}" if v.get("peg") is not None else "—", "fwd P/E ÷ growth", _peg_col(v.get("peg"))),
    ("EV/EBITDA", _x(v.get("ev_ebitda")), "TTM", C["purple"]),
    ("Rev Growth", _g(v.get("rev_growth")), "latest qtr, YoY", C["green"] if (v.get("rev_growth") or 0) >= 0 else C["red"]),
    ("Net Profit Growth", _g(v.get("earnings_growth")), "latest qtr, YoY", C["green"] if (v.get("earnings_growth") or 0) >= 0 else C["red"]),
    ("Gross Margin", _x(v.get("gross_margin"), "%"), "TTM", C["green"] if (v.get("gross_margin") or 0) > 40 else C["text"]),
    ("Net Margin", _x(v.get("net_margin"), "%"), "TTM, GAAP", C["green"] if (v.get("net_margin") or 0) > 10 else C["text"]),
]
tiles_html = '<div class="tilegrid">' + "".join(
    f'<div class="tile"><div class="lab">{esc(lab)}</div>'
    f'<div class="val" style="color:{col};">{esc(val)}</div>'
    f'<div class="nt">{esc(note)}</div></div>'
    for lab, val, note, col in tiles
) + "</div>"
st.markdown(tiles_html, unsafe_allow_html=True)

# ── daily price + 20-day MA (full width) ─────────────────────────────────────
pd_ = d.get("price_daily")
if pd_:
    st.markdown('<div class="erh">Daily Price &amp; 20-day Moving Average '
                '<span class="sub">— last ~12 months</span></div>', unsafe_allow_html=True)
    xi, tv, tt = _idx_ticks(pd_["dates"])
    cd = [_tick(s) for s in pd_["dates"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xi, y=pd_["close"], name="Close",
                             line=dict(color=C["blue"], width=2),
                             fill="tozeroy", fillcolor="rgba(88,166,255,0.07)",
                             customdata=cd, hovertemplate="%{customdata}<br>$%{y:.2f}<extra>Close</extra>"))
    fig.add_trace(go.Scatter(x=xi, y=pd_["ma20"], name="20-day MA",
                             line=dict(color=C["sub"], width=1.3, dash="dash"),
                             customdata=cd, hovertemplate="%{customdata}<br>$%{y:.2f}<extra>MA20</extra>"))
    lo = min(pd_["close"]) * 0.97
    hi = max(pd_["close"]) * 1.03
    fig.update_yaxes(range=[lo, hi], tickprefix="$")
    fig.update_xaxes(tickmode="array", tickvals=tv, ticktext=tt)
    fig = _base_layout(fig, 360)
    fig.update_layout(hovermode="closest")
    st.plotly_chart(fig, use_container_width=True, config=_CHART_CFG)
    st.caption("Where price holds the 20-day line often marks short-term support.")

# ── relative performance | risk & capital return ─────────────────────────────
left, right = st.columns([2, 1])
with left:
    ch = d.get("chart")
    st.markdown(f'<div class="erh">{esc(d["ticker"])} vs S&amp;P 500 — 1-Year Relative Performance</div>',
                unsafe_allow_html=True)
    if ch:
        xi, tv, tt = _idx_ticks(ch["dates"])
        cd = [_tick(s) for s in ch["dates"]]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=xi, y=ch["spy"], name="S&P 500",
                                 line=dict(color=C["sub"], width=1.4, dash="dash"),
                                 customdata=cd, hovertemplate="%{customdata}<br>%{y:.1f}<extra>S&P 500</extra>"))
        fig.add_trace(go.Scatter(x=xi, y=ch["stock"], name=d["ticker"],
                                 line=dict(color=C["blue"], width=2.2),
                                 customdata=cd, hovertemplate="%{customdata}<br>%{y:.1f}<extra>" + d["ticker"] + "</extra>"))
        ac = C["green"] if ch["alpha"] >= 0 else C["red"]
        fig.add_annotation(xref="paper", yref="paper", x=0.01, y=0.99, showarrow=False,
                           align="left", xanchor="left", yanchor="top",
                           bordercolor=ac, borderwidth=1, borderpad=4, bgcolor=C["panel"],
                           font=dict(color=ac, size=10, family="ui-monospace, monospace"),
                           text=(f"{d['ticker']}: {ch['stock_ret']:+.1f}%<br>"
                                 f"S&P 500: {ch['spy_ret']:+.1f}%<br>"
                                 f"Alpha: {ch['alpha']:+.1f}%"))
        fig.update_xaxes(tickmode="array", tickvals=tv, ticktext=tt)
        fig = _base_layout(fig, 340)
        fig.update_layout(showlegend=False, hovermode="closest")
        st.plotly_chart(fig, use_container_width=True, config=_CHART_CFG)
    else:
        st.caption("No price history available.")

    # ── valuation history (P/E line) — stacked under relative performance ──
    pe = d.get("pe_series")
    if pe:
        st.markdown(f'<div class="erh" style="margin-top:14px;">Valuation History — {esc(pe["basis"])} '
                    '<span class="sub">(last ~3 years)</span></div>', unsafe_allow_html=True)
        xi, tv, tt = _idx_ticks(pe["dates"])
        cd = [_tick(s) for s in pe["dates"]]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=xi, y=pe["pe"], name="P/E",
                                 line=dict(color=C["blue"], width=1.8),
                                 fill="tozeroy", fillcolor="rgba(88,166,255,0.06)",
                                 customdata=cd, hovertemplate="%{customdata}<br>%{y:.1f}×<extra></extra>"))
        fig.update_yaxes(ticksuffix="×")
        fig.update_xaxes(tickmode="array", tickvals=tv, ticktext=tt)
        fig = _base_layout(fig, 260)
        fig.update_layout(showlegend=False, hovermode="closest")
        st.plotly_chart(fig, use_container_width=True, config=_CHART_CFG)

with right:
    st.markdown('<div class="erh">Risk &amp; Range</div>', unsafe_allow_html=True)
    risk_rows = [
        ("1-Yr Return", _g(r.get("ret_1y")), C["green"] if (r.get("ret_1y") or 0) >= 0 else C["red"]),
        ("Ann. Volatility", _x(r.get("ann_vol"), "%"), C["yellow"]),
        ("Sharpe Ratio", f"{r['sharpe']:.2f}" if r.get("sharpe") is not None else "—",
         C["green"] if (r.get("sharpe") or 0) >= 1 else (C["text"] if (r.get("sharpe") or 0) >= 0 else C["red"])),
        ("Max Drawdown", _g(r.get("max_drawdown")), C["red"]),
        ("52W High / Low", f"${r['wk52_high']:.2f} / ${r['wk52_low']:.2f}"
            if r.get("wk52_high") is not None and r.get("wk52_low") is not None else "—", C["sub"]),
        ("52W Position", f"{r['wk52_pos']:.0f}%" if r.get("wk52_pos") is not None else "—", C["blue"]),
        ("Beta", f"{r['beta']:.2f}" if r.get("beta") is not None else "—", C["orange"]),
    ]
    rk = "<table class='rk'>" + "".join(
        f"<tr><td class='l'>{esc(a)}</td><td class='r' style='color:{col};'>{esc(b)}</td></tr>"
        for a, b, col in risk_rows
    ) + "</table>"
    st.markdown(rk, unsafe_allow_html=True)

    cap = [c for c in (d.get("capital_return") or [])
           if c.get("net_income") and (c.get("buyback_pct") is not None or c.get("dividend_pct") is not None)]
    if cap:
        st.markdown('<div class="erh" style="margin-top:14px;">Capital Return '
                    '<span class="sub">(% of net income)</span></div>', unsafe_allow_html=True)
        yrs = [str(c["year"]) for c in cap]
        fig = go.Figure()
        fig.add_trace(go.Bar(y=yrs, x=[c.get("buyback_pct") or 0 for c in cap], name="Buybacks",
                             orientation="h", marker_color=C["blue"]))
        fig.add_trace(go.Bar(y=yrs, x=[c.get("dividend_pct") or 0 for c in cap], name="Dividends",
                             orientation="h", marker_color=C["green"]))
        fig.update_layout(barmode="stack", hovermode="y unified")
        fig.update_xaxes(ticksuffix="%", gridcolor=C["border"])
        fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
        st.plotly_chart(_base_layout(fig, 220), use_container_width=True, config=_CHART_CFG)

# ── quarterly revenue/profit | cash flow ─────────────────────────────────────
ic = [c for c in (d.get("income_q") or []) if c.get("revenue") is not None or c.get("net_income") is not None]
cf = [c for c in (d.get("cash_flow") or []) if c.get("ocf") is not None or c.get("fcf") is not None]
qa, qb = st.columns(2)
with qa:
    st.markdown('<div class="erh">Revenue &amp; Net Profit <span class="sub">(quarterly)</span></div>',
                unsafe_allow_html=True)
    if ic:
        fig = go.Figure()
        labels = [c["label"] for c in ic]
        fig.add_trace(go.Bar(x=labels, y=[c.get("revenue") for c in ic], name="Revenue", marker_color=C["blue"]))
        fig.add_trace(go.Bar(x=labels, y=[c.get("net_income") for c in ic], name="Net Profit", marker_color=C["green"]))
        fig.update_layout(barmode="group", hovermode="x", bargap=0.5, bargroupgap=0.15)
        st.plotly_chart(_base_layout(fig, 300), use_container_width=True, config=_CHART_CFG)
    else:
        st.caption("No quarterly income data available.")
with qb:
    st.markdown('<div class="erh">Cash Flow — Operating vs Free <span class="sub">(quarterly)</span></div>',
                unsafe_allow_html=True)
    if cf:
        fig = go.Figure()
        labels = [c["label"] for c in cf]
        fig.add_trace(go.Bar(x=labels, y=[c.get("ocf") for c in cf], name="Operating CF", marker_color=C["green"]))
        fig.add_trace(go.Bar(x=labels, y=[c.get("fcf") for c in cf], name="Free CF", marker_color=C["blue"]))
        fig.update_layout(barmode="group", hovermode="x", bargap=0.5, bargroupgap=0.15)
        st.plotly_chart(_base_layout(fig, 300), use_container_width=True, config=_CHART_CFG)
    else:
        st.caption("No cash flow data available.")

# ── peer comparison table ────────────────────────────────────────────────────
target = [dict(p, _t=True) for p in ([d["target"]] if d.get("target") else [])]
peers = sorted([dict(p, _t=False) for p in (d.get("peers") or [])],
               key=lambda x: x.get("market_cap") or 0, reverse=True)
ordered = target + peers
if ordered:
    st.markdown('<div class="erh">Peer Comparison</div>', unsafe_allow_html=True)
    head = ("<tr><th class='l'>Ticker</th><th class='l'>Company</th><th>Price</th><th>Mkt Cap</th>"
            "<th>Fwd P/E</th><th>P/E TTM</th><th>Div Yld</th><th>52W Pos</th></tr>")
    body = ""
    for p in ordered:
        tcol = C["orange"] if p["_t"] else C["text"]
        body += (
            f"<tr class='{'tgt' if p['_t'] else ''}'>"
            f"<td class='l' style='font-weight:700;color:{tcol};'>{esc(p.get('ticker','—'))}</td>"
            f"<td class='l' style='color:{C['sub']};'>{esc((p.get('name') or '')[:34])}</td>"
            f"<td>{('$%.2f' % p['current_price']) if p.get('current_price') is not None else '—'}</td>"
            f"<td>{fmt_mc(p.get('market_cap'))}</td>"
            f"<td style='color:{C['yellow']};'>{('%.1f×' % p['forward_pe']) if p.get('forward_pe') is not None else '—'}</td>"
            f"<td style='color:{C['sub']};'>{('%.1f×' % p['trailing_pe']) if p.get('trailing_pe') is not None else '—'}</td>"
            f"<td>{('%.2f%%' % p['dividend_yield']) if p.get('dividend_yield') is not None else '—'}</td>"
            f"<td style='color:{C['blue']};'>{('%.0f%%' % p['price_position_pct']) if p.get('price_position_pct') is not None else '—'}</td>"
            f"</tr>"
        )
    st.markdown(f"<div class='ptwrap'><table class='pt'>{head}{body}</table></div>", unsafe_allow_html=True)

    # ── bubble chart: x=52w position, y=fwd P/E, size=market cap ──────────────
    pts = [p for p in ordered
           if p.get("price_position_pct") is not None and p.get("forward_pe") and p["forward_pe"] > 0
           and p.get("market_cap") and p["market_cap"] > 0]
    if pts:
        st.markdown('<div class="erh" style="margin-top:14px;">Peer Map — Valuation vs Momentum</div>',
                    unsafe_allow_html=True)
        st.caption(f"X = 52-week position (momentum) · Y = forward P/E (valuation) · "
                   f"bubble size = market cap · {d['ticker']} highlighted.")
        big = max(p["market_cap"] for p in pts)
        fig = go.Figure()
        for p in pts:
            is_t = p["_t"]
            fig.add_trace(go.Scatter(
                x=[p["price_position_pct"]], y=[p["forward_pe"]],
                mode="markers+text", text=[p["ticker"]], textposition="middle center",
                textfont=dict(size=9, color=C["text"]),
                marker=dict(size=[p["market_cap"]], sizemode="area",
                            sizeref=2.0 * big / (70.0 ** 2), sizemin=8,
                            color=C["orange"] if is_t else C["blue"],
                            opacity=0.85 if is_t else 0.45,
                            line=dict(width=2 if is_t else 1, color=C["orange"] if is_t else C["blue"])),
                showlegend=False,
                hovertemplate=f"{p['ticker']}<br>52W pos: %{{x:.0f}}%<br>Fwd P/E: %{{y:.1f}}×<extra></extra>",
            ))
        fig.update_xaxes(title_text="52-Week Position (low → high)", ticksuffix="%")
        fig.update_yaxes(title_text="Forward P/E", ticksuffix="×")
        fig.update_layout(hovermode="closest")
        st.plotly_chart(_base_layout(fig, 430), use_container_width=True, config=_CHART_CFG)

st.divider()
st.caption("Built with Streamlit · data from Yahoo Finance. Figures may include GAAP one-time "
           "items and can differ from company-reported non-GAAP numbers. Not investment advice.")
