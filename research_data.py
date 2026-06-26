"""
research_data.py
================
Standalone data layer for the Equity Research web app.

Builds a single structured payload (valuation, risk, relative-performance,
moving-average price series, trailing P/E line, quarterly revenue/profit,
quarterly cash flow, capital return, and peer comparison) for one ticker.

Reuses EquityResearchReport (equity_research.py) for the heavy lifting —
company info, S&P 500 peer discovery, and EPS extraction — but does NOT
render any images. All numbers come from Yahoo Finance via yfinance.
"""

import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

from equity_research import EquityResearchReport


# ── small helpers ────────────────────────────────────────────────────────────
def _f(v):
    """Coerce to float, mapping None/NaN/garbage to None."""
    try:
        if v is None:
            return None
        x = float(v)
        return None if x != x else x
    except Exception:
        return None


def _pct(v):
    x = _f(v)
    return round(x * 100, 1) if x is not None else None


def _sanitize(obj):
    """Replace NaN/Inf floats with None so the payload is JSON/Arrow safe."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def _mc_str(market_cap):
    v = market_cap or 0
    if v >= 1e12:
        return f"${v / 1e12:.2f}T"
    if v >= 1e9:
        return f"${v / 1e9:.2f}B"
    if v >= 1e6:
        return f"${v / 1e6:.0f}M"
    return "N/A"


def _row_by_year(df, names, exact_first=True):
    if df is None or getattr(df, "empty", True):
        return {}
    low = {str(i).strip().lower(): i for i in df.index}
    target = None
    if exact_first:
        for nm in names:
            if nm in low:
                target = low[nm]; break
    if target is None:
        for i in df.index:
            sl = str(i).strip().lower()
            if any(nm in sl for nm in names):
                target = i; break
    if target is None:
        return {}
    res = {}
    for col, val in df.loc[target].items():
        v = _f(val)
        yr = getattr(col, "year", None)
        if v is not None and yr:
            res[int(yr)] = v
    return res


def _row_by_period(df, names):
    """Sorted list of (Timestamp, value) for the first matching row label."""
    if df is None or getattr(df, "empty", True):
        return []
    low = {str(i).strip().lower(): i for i in df.index}
    target = None
    for nm in names:
        if nm in low:
            target = low[nm]; break
    if target is None:
        for i in df.index:
            sl = str(i).strip().lower()
            if any(nm in sl for nm in names):
                target = i; break
    if target is None:
        return []
    rows = []
    for col, val in df.loc[target].items():
        v = _f(val)
        try:
            ts = pd.Timestamp(col)
        except Exception:
            continue
        if v is not None:
            rows.append((ts, v))
    rows.sort(key=lambda x: x[0])
    return rows


def _qlabel(ts):
    q = (ts.month - 1) // 3 + 1
    return f"Q{q} '{str(ts.year)[2:]}"


def _clean_peer(p):
    if not p:
        return None
    return {
        "ticker":             p.get("ticker"),
        "name":               p.get("name"),
        "forward_pe":         _f(p.get("forward_pe")),
        "trailing_pe":        _f(p.get("trailing_pe")),
        "dividend_yield":     _f(p.get("dividend_yield")),
        "market_cap":         _f(p.get("market_cap")),
        "price_position_pct": _f(p.get("price_position_pct")),
        "current_price":      _f(p.get("current_price")),
    }


# ── main entry point ─────────────────────────────────────────────────────────
def build_payload(ticker):
    """Construct the full research payload for `ticker`.

    Raises ValueError if the ticker can't be loaded.
    """
    report = EquityResearchReport(ticker)
    if not report.stock or not report.info:
        raise ValueError(
            f"Could not load data for '{ticker}'. Check the symbol and try again."
        )

    info = report.info or {}
    current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0

    out = {
        "ticker":         report.ticker,
        "company_name":   report.company_name or report.ticker,
        "sector":         report.sector,
        "industry":       report.industry,
        "current_price":  float(current_price or 0),
        "market_cap_str": _mc_str(report.market_cap),
        "valuation": {}, "risk": {}, "chart": None,
        "price_daily": None, "pe_series": None,
        "capital_return": [], "buybacks": [],
        "cash_flow": [], "income_q": [],
        "peers": [], "target": None,
    }

    # ── Valuation ────────────────────────────────────────────────────
    try:
        out["valuation"] = {
            "current_price": _f(info.get("currentPrice")) or _f(info.get("regularMarketPrice")),
            "market_cap":    _f(report.market_cap),
            "pe_ttm":        _f(info.get("trailingPE")),
            "fwd_pe":        _f(info.get("forwardPE")),
            "peg":           _f(report.calculate_peg_ratio()),
            "ev_ebitda":     _f(info.get("enterpriseToEbitda")),
            "eps_ttm":       _f(report.get_current_ttm_eps()),
            "eps_fwd":       _f(info.get("forwardEps")),
            "rev_growth":      _pct(info.get("revenueGrowth")),
            "earnings_growth": _pct(info.get("earningsGrowth")),
            "gross_margin":    _pct(info.get("grossMargins")),
            "net_margin":      _pct(info.get("profitMargins")),
            "div_yield":     _f(report.calculate_dividend_yield()),
            "beta":          _f(info.get("beta")),
        }
    except Exception as e:
        print(f"  [research] valuation build failed: {e}")

    # ── Risk + 1y relative-performance chart vs S&P 500 ──────────────
    try:
        end = datetime.now()
        start = end - timedelta(days=365)
        hist = report.stock.history(start=start, end=end)
        if hist is not None and not hist.empty:
            if getattr(hist.index, "tz", None) is not None:
                hist.index = hist.index.tz_localize(None)
            closes = hist["Close"].dropna()
            rets = closes.pct_change().dropna()
            ret_1y = (closes.iloc[-1] / closes.iloc[0] - 1) * 100
            vol = float(rets.std() * np.sqrt(252) * 100) if len(rets) else None
            rf_d = 0.045 / 252
            sharpe = float((rets - rf_d).mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0.0
            cumr = (1 + rets).cumprod()
            max_dd = float(((cumr - cumr.cummax()) / cumr.cummax()).min() * 100) if len(rets) else None
            w52_hi = _f(info.get("fiftyTwoWeekHigh")) or float(closes.max())
            w52_lo = _f(info.get("fiftyTwoWeekLow")) or float(closes.min())
            curr = float(closes.iloc[-1])
            pos52 = ((curr - w52_lo) / (w52_hi - w52_lo) * 100) if w52_hi > w52_lo else 50
            out["risk"] = {
                "ret_1y": round(float(ret_1y), 1),
                "ann_vol": round(vol, 1) if vol is not None else None,
                "sharpe": round(sharpe, 2),
                "max_drawdown": round(max_dd, 1) if max_dd is not None else None,
                "wk52_high": round(w52_hi, 2),
                "wk52_low": round(w52_lo, 2),
                "wk52_pos": round(float(pos52), 0),
                "beta": out["valuation"].get("beta"),
            }
            try:
                spy = yf.Ticker("SPY").history(start=start, end=end)
                if spy is not None and not spy.empty:
                    if getattr(spy.index, "tz", None) is not None:
                        spy.index = spy.index.tz_localize(None)
                    spy_al = spy["Close"].reindex(closes.index, method="ffill").bfill()
                    s_norm = closes / closes.iloc[0] * 100
                    p_norm = spy_al / spy_al.iloc[0] * 100
                    T = len(s_norm)
                    n = min(120, T)
                    idx = sorted(set(np.linspace(0, T - 1, n).astype(int).tolist()))
                    out["chart"] = {
                        "ticker": report.ticker,
                        "dates": [closes.index[i].strftime("%b %Y") for i in idx],
                        "stock": [round(float(s_norm.iloc[i]), 2) for i in idx],
                        "spy": [round(float(p_norm.iloc[i]), 2) for i in idx],
                        "stock_ret": round(float(s_norm.iloc[-1] - 100), 1),
                        "spy_ret": round(float(p_norm.iloc[-1] - 100), 1),
                        "alpha": round(float((s_norm.iloc[-1] - 100) - (p_norm.iloc[-1] - 100)), 1),
                    }
            except Exception as e:
                print(f"  [research] relative chart failed: {e}")
    except Exception as e:
        print(f"  [research] risk build failed: {e}")

    # ── Peers (table + bubble chart) ─────────────────────────────────
    try:
        out["target"] = _clean_peer(report.get_target_company_data())
    except Exception as e:
        print(f"  [research] target data failed: {e}")
    try:
        out["peers"] = [_clean_peer(p) for p in (report.get_peer_data_with_forward_pe() or []) if p]
    except Exception as e:
        print(f"  [research] peers failed: {e}")

    # ── Statement frames ─────────────────────────────────────────────
    cf = getattr(report.stock, "cashflow", None)
    istmt = getattr(report.stock, "income_stmt", None)
    if istmt is None or getattr(istmt, "empty", True):
        istmt = getattr(report.stock, "financials", None)

    net_income = _row_by_year(istmt, ["net income"])
    buyback_y  = _row_by_year(cf, ["repurchase of capital stock", "repurchase of common stock"])
    dividend_y = _row_by_year(cf, ["cash dividends paid", "common stock dividend paid",
                                   "common stock dividends paid", "dividends paid"])

    # Capital return: buybacks + dividends as % of net income
    try:
        years = sorted(set(buyback_y) | set(dividend_y) | set(net_income))
        cap = []
        for yr in years:
            bb = abs(buyback_y[yr]) if yr in buyback_y else None
            dv = abs(dividend_y[yr]) if yr in dividend_y else None
            ni = net_income.get(yr)
            cap.append({
                "year": int(yr),
                "buyback": round(bb, 0) if bb is not None else None,
                "dividend": round(dv, 0) if dv is not None else None,
                "net_income": round(ni, 0) if ni is not None else None,
                "buyback_pct": round(bb / ni * 100, 1) if (bb is not None and ni and ni > 0) else None,
                "dividend_pct": round(dv / ni * 100, 1) if (dv is not None and ni and ni > 0) else None,
            })
        out["capital_return"] = cap[-4:]
        out["buybacks"] = [{"year": c["year"], "amount": c["buyback"]}
                           for c in out["capital_return"] if c["buyback"]]
    except Exception as e:
        print(f"  [research] capital return failed: {e}")

    # Quarterly cash flow (latest 4)
    try:
        qcf = getattr(report.stock, "quarterly_cashflow", None)
        ocf_q   = dict(_row_by_period(qcf, ["operating cash flow", "total cash from operating activities"]))
        fcf_q   = dict(_row_by_period(qcf, ["free cash flow"]))
        capex_q = dict(_row_by_period(qcf, ["capital expenditure", "capital expenditures"]))
        periods = sorted(set(ocf_q) | set(fcf_q) | set(capex_q))
        rows = []
        for ts in periods:
            ocf = ocf_q.get(ts); fcf = fcf_q.get(ts); capex = capex_q.get(ts)
            if fcf is None and ocf is not None and capex is not None:
                fcf = ocf + capex
            rows.append({
                "label": _qlabel(ts),
                "ocf": round(ocf, 0) if ocf is not None else None,
                "fcf": round(fcf, 0) if fcf is not None else None,
            })
        out["cash_flow"] = rows[-4:]
    except Exception as e:
        print(f"  [research] quarterly cash flow failed: {e}")

    # Quarterly revenue + net profit (latest 4)
    try:
        qis = getattr(report.stock, "quarterly_income_stmt", None)
        if qis is None or getattr(qis, "empty", True):
            qis = getattr(report.stock, "quarterly_financials", None)
        rev_q = dict(_row_by_period(qis, ["total revenue", "operating revenue", "revenue"]))
        ni_q  = dict(_row_by_period(qis, ["net income"]))
        periods = sorted(set(rev_q) | set(ni_q))
        rows = []
        for ts in periods:
            rows.append({
                "label": _qlabel(ts),
                "revenue": round(rev_q[ts], 0) if ts in rev_q else None,
                "net_income": round(ni_q[ts], 0) if ts in ni_q else None,
            })
        out["income_q"] = rows[-4:]
    except Exception as e:
        print(f"  [research] quarterly income failed: {e}")

    # Daily price + 20-day MA, and 3y trailing P/E line
    try:
        ph = report.stock.history(period="3y")
        if ph is not None and not ph.empty:
            if getattr(ph.index, "tz", None) is not None:
                ph.index = ph.index.tz_localize(None)
            close = ph["Close"].dropna()
            ma20 = close.rolling(20).mean()
            ma50 = close.rolling(50).mean()

            def _r2(s, d):
                v = s.get(d)
                return None if (v is None or v != v) else round(float(v), 2)

            disp = close.index[-260:]
            out["price_daily"] = {
                "dates": [d.strftime("%Y-%m-%d") for d in disp],
                "close": [round(float(close[d]), 2) for d in disp],
                "ma20":  [_r2(ma20, d) for d in disp],
                "ma50":  [_r2(ma50, d) for d in disp],
            }

            anchors = {}
            for ts, e in (_row_by_period(istmt, ["diluted eps"]) or _row_by_period(istmt, ["basic eps"])):
                if e and e > 0:
                    anchors[pd.Timestamp(ts).normalize()] = e
            qstmt = getattr(report.stock, "quarterly_income_stmt", None)
            if qstmt is None or getattr(qstmt, "empty", True):
                qstmt = getattr(report.stock, "quarterly_financials", None)
            qeps = []
            for want in (["diluted eps"], ["basic eps"]):
                qeps = _row_by_period(qstmt, want)
                if qeps:
                    break
            for i in range(3, len(qeps)):
                ttm = sum(e for _, e in qeps[i - 3:i + 1])
                if ttm and ttm > 0:
                    anchors[pd.Timestamp(qeps[i][0]).normalize()] = ttm
            ttm_now = _f(report.get_current_ttm_eps())
            if ttm_now and ttm_now > 0:
                anchors[pd.Timestamp.today().normalize()] = ttm_now

            if len(anchors) >= 2:
                items = sorted(anchors.items())
                ax = np.array([t.value for t, _ in items], dtype=float)
                ay = np.array([v for _, v in items], dtype=float)
                T = len(close)
                n = min(240, T)
                idx = sorted(set(np.linspace(0, T - 1, n).astype(int).tolist()))
                dts, pes = [], []
                for i in idx:
                    d = close.index[i]
                    eps = float(np.interp(float(d.value), ax, ay))
                    if eps > 0:
                        dts.append(d.strftime("%Y-%m-%d"))
                        pes.append(round(float(close.iloc[i] / eps), 1))
                if len(pes) >= 8:
                    out["pe_series"] = {"dates": dts, "pe": pes, "basis": "Trailing P/E"}
    except Exception as e:
        print(f"  [research] price/pe series failed: {e}")

    return _sanitize(out)
