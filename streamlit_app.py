"""
Equity Research — Streamlit web app
===================================
A free, no-login equity research dashboard: enter a ticker and get valuation
metrics, price action with a moving average, relative performance vs the S&P 500,
risk stats, capital return, a 3-year trailing P/E line, quarterly revenue / profit
and cash flow, plus a peer comparison table and valuation-vs-momentum bubble map.

Data: Yahoo Finance (via yfinance). For research/education only — not investment advice.
"""

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


# ── formatting helpers ───────────────────────────────────────────────────────
def fmt_bn(v):
    if v is None:
        return "—"
    a, s = abs(v), "-" if v < 0 else ""
    if a >= 1e9:
        return f"{s}${a/1e9:.0f}B" if a >= 1e10 else f"{s}${a/1e9:.1f}B"
    if a >= 1e6:
        return f"{s}${a/1e6:.0f}M"
    return f"{s}${a:.0f}"


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


def _base_layout(fig, height=320):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=C["bg"],
        font=dict(family="monospace", size=11, color=C["sub"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
        xaxis=dict(gridcolor=C["border"], zeroline=False),
        yaxis=dict(gridcolor=C["border"], zeroline=False),
        hovermode="x unified",
    )
    return fig


@st.cache_data(ttl=900, show_spinner=False)
def load(ticker):
    return build_payload(ticker)


# ── header / input ───────────────────────────────────────────────────────────
st.title("📈 Equity Research")
st.caption("Free research dashboard — enter a ticker for valuation, price action, "
           "cash flow and peers. Data: Yahoo Finance · for research only, not investment advice.")

col_in, col_btn = st.columns([4, 1])
with col_in:
    ticker = st.text_input("Ticker symbol", value="", placeholder="e.g. AAPL, MSFT, NVDA",
                           label_visibility="collapsed").strip().upper()
with col_btn:
    go_clicked = st.button("Generate report", type="primary", use_container_width=True)

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

# ── company header ───────────────────────────────────────────────────────────
h1, h2 = st.columns([3, 1])
with h1:
    st.subheader(f"{d['company_name']}  ·  {d['ticker']}")
    st.caption(f"{d.get('sector','')}{' · ' + d['industry'] if d.get('industry') else ''}")
with h2:
    st.metric("Price", f"${d['current_price']:.2f}", help="Latest price (Yahoo Finance)")
    st.caption(f"Market cap {d['market_cap_str']}")

# ── valuation tiles ──────────────────────────────────────────────────────────
def _x(x, suf="×"):
    return f"{x:.1f}{suf}" if x is not None else "—"

def _g(x):
    return (f"+{x:.1f}%" if x >= 0 else f"{x:.1f}%") if x is not None else "—"

tiles = [
    ("P/E TTM",  _x(v.get("pe_ttm")),  "trailing 12-mo"),
    ("Fwd P/E",  _x(v.get("fwd_pe")),  "next-yr estimate"),
    ("PEG",      f"{v['peg']:.2f}" if v.get("peg") is not None else "—", "fwd P/E ÷ growth"),
    ("EV/EBITDA", _x(v.get("ev_ebitda")), "TTM"),
    ("Rev Growth", _g(v.get("rev_growth")), "latest qtr, YoY"),
    ("Net Profit Growth", _g(v.get("earnings_growth")), "latest qtr, YoY"),
    ("Gross Margin", _x(v.get("gross_margin"), "%"), "TTM"),
    ("Net Margin", _x(v.get("net_margin"), "%"), "TTM, GAAP"),
]
cols = st.columns(4)
for i, (label, val, note) in enumerate(tiles):
    with cols[i % 4]:
        st.metric(label, val, help=note)
        st.caption(note)

st.divider()

# ── daily price + 20-day MA (full width) ─────────────────────────────────────
pd_ = d.get("price_daily")
if pd_:
    st.markdown("#### Daily Price & 20-day Moving Average — last ~12 months")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pd_["dates"], y=pd_["close"], name="Close",
                             line=dict(color=C["blue"], width=2),
                             fill="tozeroy", fillcolor="rgba(88,166,255,0.08)"))
    fig.add_trace(go.Scatter(x=pd_["dates"], y=pd_["ma20"], name="20-day MA",
                             line=dict(color=C["sub"], width=1.3, dash="dash")))
    lo = min(x for x in pd_["close"]) * 0.97
    hi = max(x for x in pd_["close"]) * 1.03
    fig.update_yaxes(range=[lo, hi], tickprefix="$")
    st.plotly_chart(_base_layout(fig, 360), use_container_width=True,
                    config={"displayModeBar": False})
    st.caption("Where price holds the 20-day line often marks short-term support.")

# ── relative performance | risk & capital return ─────────────────────────────
left, right = st.columns([2, 1])
with left:
    ch = d.get("chart")
    st.markdown(f"#### {d['ticker']} vs S&P 500 — 1-Year Relative Performance")
    if ch:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ch["dates"], y=ch["stock"], name=d["ticker"],
                                 line=dict(color=C["blue"], width=2),
                                 fill="tonexty", fillcolor="rgba(88,166,255,0.06)"))
        fig.add_trace(go.Scatter(x=ch["dates"], y=ch["spy"], name="S&P 500",
                                 line=dict(color=C["sub"], width=1.4, dash="dash")))
        ac = C["green"] if ch["alpha"] >= 0 else C["red"]
        fig.add_annotation(xref="paper", yref="paper", x=0.02, y=0.98, showarrow=False,
                           align="left", bordercolor=ac, borderwidth=1, bgcolor=C["panel"],
                           font=dict(color=ac, size=11),
                           text=(f"{d['ticker']}: {ch['stock_ret']:+.1f}%<br>"
                                 f"S&P 500: {ch['spy_ret']:+.1f}%<br>"
                                 f"Alpha: {ch['alpha']:+.1f}%"))
        st.plotly_chart(_base_layout(fig, 340), use_container_width=True,
                        config={"displayModeBar": False})
    else:
        st.caption("No price history available.")

with right:
    st.markdown("#### Risk & Range")
    risk_rows = [
        ("1-Yr Return", _g(r.get("ret_1y"))),
        ("Ann. Volatility", _x(r.get("ann_vol"), "%")),
        ("Sharpe Ratio", f"{r['sharpe']:.2f}" if r.get("sharpe") is not None else "—"),
        ("Max Drawdown", _g(r.get("max_drawdown"))),
        ("52W High / Low", f"${r['wk52_high']:.2f} / ${r['wk52_low']:.2f}"
            if r.get("wk52_high") is not None and r.get("wk52_low") is not None else "—"),
        ("52W Position", f"{r['wk52_pos']:.0f}%" if r.get("wk52_pos") is not None else "—"),
        ("Beta", f"{r['beta']:.2f}" if r.get("beta") is not None else "—"),
    ]
    st.table({"Metric": [a for a, _ in risk_rows], "Value": [b for _, b in risk_rows]})

    cap = [c for c in (d.get("capital_return") or [])
           if c.get("net_income") and (c.get("buyback_pct") is not None or c.get("dividend_pct") is not None)]
    if cap:
        st.markdown("#### Capital Return (% of net income)")
        fig = go.Figure()
        yrs = [str(c["year"]) for c in cap]
        fig.add_trace(go.Bar(y=yrs, x=[c.get("buyback_pct") or 0 for c in cap], name="Buybacks",
                             orientation="h", marker_color=C["blue"]))
        fig.add_trace(go.Bar(y=yrs, x=[c.get("dividend_pct") or 0 for c in cap], name="Dividends",
                             orientation="h", marker_color=C["green"]))
        fig.update_layout(barmode="stack")
        fig.update_xaxes(ticksuffix="%")
        st.plotly_chart(_base_layout(fig, 230), use_container_width=True,
                        config={"displayModeBar": False})

st.divider()

# ── valuation history (P/E line, full width) ─────────────────────────────────
pe = d.get("pe_series")
if pe:
    st.markdown(f"#### Valuation History — {pe['basis']} (last ~3 years)")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pe["dates"], y=pe["pe"], name="P/E",
                             line=dict(color=C["blue"], width=1.8),
                             fill="tozeroy", fillcolor="rgba(88,166,255,0.06)"))
    fig.update_yaxes(ticksuffix="×")
    st.plotly_chart(_base_layout(fig, 300), use_container_width=True,
                    config={"displayModeBar": False})

# ── quarterly revenue/profit | cash flow ─────────────────────────────────────
ic = [c for c in (d.get("income_q") or []) if c.get("revenue") is not None or c.get("net_income") is not None]
cf = [c for c in (d.get("cash_flow") or []) if c.get("ocf") is not None or c.get("fcf") is not None]
qa, qb = st.columns(2)
with qa:
    st.markdown("#### Revenue & Net Profit (quarterly)")
    if ic:
        fig = go.Figure()
        labels = [c["label"] for c in ic]
        fig.add_trace(go.Bar(x=labels, y=[c.get("revenue") for c in ic], name="Revenue", marker_color=C["blue"]))
        fig.add_trace(go.Bar(x=labels, y=[c.get("net_income") for c in ic], name="Net Profit", marker_color=C["green"]))
        fig.update_layout(barmode="group")
        st.plotly_chart(_base_layout(fig, 300), use_container_width=True, config={"displayModeBar": False})
    else:
        st.caption("No quarterly income data available.")
with qb:
    st.markdown("#### Cash Flow — Operating vs Free (quarterly)")
    if cf:
        fig = go.Figure()
        labels = [c["label"] for c in cf]
        fig.add_trace(go.Bar(x=labels, y=[c.get("ocf") for c in cf], name="Operating CF", marker_color=C["green"]))
        fig.add_trace(go.Bar(x=labels, y=[c.get("fcf") for c in cf], name="Free CF", marker_color=C["blue"]))
        fig.update_layout(barmode="group")
        st.plotly_chart(_base_layout(fig, 300), use_container_width=True, config={"displayModeBar": False})
    else:
        st.caption("No cash flow data available.")

st.divider()

# ── peer comparison table ────────────────────────────────────────────────────
target = [dict(p, _t=True) for p in ([d["target"]] if d.get("target") else [])]
peers = sorted([dict(p, _t=False) for p in (d.get("peers") or [])],
               key=lambda x: x.get("market_cap") or 0, reverse=True)
ordered = target + peers
if ordered:
    st.markdown("#### Peer Comparison")
    table = {
        "Ticker": [p.get("ticker", "—") for p in ordered],
        "Company": [p.get("name", "") for p in ordered],
        "Price": [f"${p['current_price']:.2f}" if p.get("current_price") is not None else "—" for p in ordered],
        "Mkt Cap": [fmt_mc(p.get("market_cap")) for p in ordered],
        "Fwd P/E": [f"{p['forward_pe']:.1f}×" if p.get("forward_pe") is not None else "—" for p in ordered],
        "P/E TTM": [f"{p['trailing_pe']:.1f}×" if p.get("trailing_pe") is not None else "—" for p in ordered],
        "Div Yld": [f"{p['dividend_yield']:.2f}%" if p.get("dividend_yield") is not None else "—" for p in ordered],
        "52W Pos": [f"{p['price_position_pct']:.0f}%" if p.get("price_position_pct") is not None else "—" for p in ordered],
    }
    st.dataframe(table, use_container_width=True, hide_index=True)

    # ── bubble chart: x=52w position, y=fwd P/E, size=market cap ──────────────
    pts = [p for p in ordered
           if p.get("price_position_pct") is not None and p.get("forward_pe") and p["forward_pe"] > 0
           and p.get("market_cap") and p["market_cap"] > 0]
    if pts:
        st.markdown("#### Peer Map — Valuation vs Momentum")
        st.caption("X = 52-week position (momentum) · Y = forward P/E (valuation) · "
                   f"bubble size = market cap · {d['ticker']} highlighted.")
        fig = go.Figure()
        for p in pts:
            is_t = p["_t"]
            fig.add_trace(go.Scatter(
                x=[p["price_position_pct"]], y=[p["forward_pe"]],
                mode="markers+text", text=[p["ticker"]], textposition="middle center",
                textfont=dict(size=9, color=C["text"]),
                marker=dict(size=[p["market_cap"]], sizemode="area",
                            sizeref=2.0 * max(q["market_cap"] for q in pts) / (70.0 ** 2),
                            sizemin=8,
                            color=C["orange"] if is_t else C["blue"],
                            opacity=0.85 if is_t else 0.45,
                            line=dict(width=2 if is_t else 1,
                                      color=C["orange"] if is_t else C["blue"])),
                name=p["ticker"], showlegend=False,
                hovertemplate=f"{p['ticker']}<br>52W pos: %{{x:.0f}}%<br>Fwd P/E: %{{y:.1f}}×<extra></extra>",
            ))
        fig.update_xaxes(title_text="52-Week Position (low → high)", ticksuffix="%")
        fig.update_yaxes(title_text="Forward P/E", ticksuffix="×")
        st.plotly_chart(_base_layout(fig, 430), use_container_width=True,
                        config={"displayModeBar": False})

st.divider()
st.caption("Built with Streamlit · data from Yahoo Finance. Figures may include GAAP one-time "
           "items and can differ from company-reported non-GAAP numbers. Not investment advice.")
