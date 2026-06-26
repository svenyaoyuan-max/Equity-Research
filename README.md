# Equity Research

A free, no-login equity research dashboard. Enter a stock ticker and get a
one-page view: valuation metrics, daily price with a 20-day moving average,
1-year performance vs the S&P 500, risk stats, capital return, a 3-year
trailing P/E line, quarterly revenue / net profit and cash flow, plus a peer
comparison table and a valuation-vs-momentum bubble map.

Data comes from Yahoo Finance via [`yfinance`](https://github.com/ranaroussi/yfinance).
**For research and education only — not investment advice.**

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Then open the URL it prints (default http://localhost:8501) and type a ticker
such as `AAPL`, `MSFT`, or `NVDA`.

## Deploy (Streamlit Community Cloud — free)

1. Push this folder to a **public GitHub repo**.
2. Go to https://share.streamlit.io → **New app**.
3. Pick the repo, branch `main`, and main file `streamlit_app.py`.
4. Click **Deploy**.

## Files

| File | Purpose |
|------|---------|
| `streamlit_app.py` | The web UI (charts, tables, layout). |
| `research_data.py` | Builds the data payload for a ticker. |
| `equity_research.py` | Company info, S&P 500 peer discovery, EPS extraction. |
| `requirements.txt` | Python dependencies. |
| `.streamlit/config.toml` | Dark theme. |

## Notes

- First load for a ticker takes a few seconds (live fetch); results are cached
  for 15 minutes.
- Some figures use GAAP numbers that can include one-time items and may differ
  from a company's reported non-GAAP figures.
