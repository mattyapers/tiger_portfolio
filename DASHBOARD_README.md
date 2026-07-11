# HTML Dashboard Quick Start

## Overview

The Tiger Portfolio Tracker now generates a **self-contained HTML dashboard** alongside the Excel report. This dashboard provides a comprehensive, single-page view of your portfolio with 4 integrated sections.

## Accessing the Dashboard

### After Running the Pipeline
```bash
# Run the pipeline (any mode)
python main.py

# Or specific modes
python main.py --yf-only
python main.py --offline

# Or generate dashboard directly from latest snapshot
python modules/dashboard.py
```

**Output:** `output/dashboard.html`

Simply open this file in any web browser (Chrome, Firefox, Safari, Edge).

### Direct File Access
- Navigate to the `output/` folder
- Double-click `dashboard.html` to open in your default browser
- Or drag it into your browser

## Dashboard Sections

### 1. Portfolio Overview
- **Total Equity** — Current portfolio market value
- **Cash Balance** — Available cash in account
- **Unrealized P&L** — Gains/losses (in dollars and %)
- **Allocation Chart** — Doughnut chart showing Core / Bonds / Satellite breakdown
- **Tier Breakdown** — Dollar amounts for each allocation tier

### 2. Stock Deep-Dive Cards
Individual cards for each holding showing:
- **Current Price** — Latest market price
- **Shares & Cost Basis** — Position sizing and average cost
- **P/E (TTM)** — Price-to-Earnings multiple
- **Gain/Loss %** — Performance vs. cost basis
- **Progress Bar** — Visual gain/loss indicator

### 3. Macro Monitor
Key economic indicators updated from official sources:
- **CPI / PCE** — Consumer and core inflation
- **Unemployment Rate** — Labor market health
- **Fed Funds Rate** — Current policy rate
- **Real GDP Growth** — Economic growth rate
- **Treasury Yields** — 10Y, 2Y, yield curve
- **DXY** — US Dollar Index strength

### 4. Technical Snapshot
Per-holding technical analysis:
- **52-Week High/Low** — Historical range
- **Distance from Highs/Lows** — % away from extremes (displayed in green if near lows)
- **50D & 200D Moving Averages** — Trend indicators
- **Relative Strength Index (RSI)** — Momentum (14-day)
  - 🟢 **Oversold** (RSI < 30) — Green box
  - 🔵 **Neutral** (RSI 30–70) — Blue box
  - 🔴 **Overbought** (RSI > 70) — Red box

## Features

✅ **Self-Contained** — Single HTML file, no external dependencies (uses free CDN charting library: Chart.js)  
✅ **Responsive Design** — Works on desktop, tablet, and mobile  
✅ **Fast Loading** — Lightweight (~73KB), no backend required  
✅ **Interactive Chart** — Allocation doughnut chart with hover tooltips  
✅ **Color-Coded Metrics** — Green for gains, red for losses, blue for neutral  
✅ **Data Source Appendix** — Includes refresh cadence and data source transparency  
✅ **Legal Disclaimer** — Standard investment disclaimer included  

## Data Refresh

| Component | Source | Cadence | Included |
|-----------|--------|---------|----------|
| Holdings & Pricing | Yahoo Finance (yfinance) | Real-time (market hours) | ✓ |
| Economic Indicators | FRED API | Daily | ✓ |
| Treasury Yields | Yahoo Finance | Real-time | ✓ |
| Technical Indicators | Calculated from 1Y price data | Daily | ✓ |

**Recommended Refresh:**
- **Daily (EOD)** for position tracking and rebalancing alerts
- **Weekly** for macro/technical trend analysis

## Customization

To modify the dashboard appearance, edit these sections in `modules/dashboard.py`:

### Colors
```python
backgroundColor: ['#1f77b4', '#2ca02c', '#ff7f0e'],  # Allocation chart
```

### Macro Data
- Set `FRED_API_KEY` environment variable to pull live FRED data
- Otherwise uses demo values (see `fetch_macro_data()`)

### Layout
The dashboard uses CSS Grid for responsive layout. Modify `.metrics-grid`, `.holdings-grid`, etc. in the `<style>` section.

## Troubleshooting

### Dashboard doesn't open
- Ensure `output/dashboard.html` exists after running the pipeline
- Try opening in a different browser
- Check file permissions (should be readable)

### Missing macro data
- FRED API requires `FRED_API_KEY` environment variable
- Dashboard falls back to demo values if key not set
- To add FRED support: `pip install fredapi` and set `FRED_API_KEY`

### Technical data incomplete
- Requires 50+ days of price history for moving averages
- Newly added holdings may show "N/A" until 50 days of data available
- Uses `yfinance` library — check internet connection

## Data Pipeline Integration

The dashboard runs automatically as **Stage 3b** in the main pipeline:

```
EXTRACT (Tiger/yfinance) → TRANSFORM (metrics) → LOAD (Excel) → DASHBOARD (HTML)
```

To run dashboard standalone:
```bash
python modules/dashboard.py
```

This reads `output/latest_snapshot.json` and generates a fresh dashboard in seconds.

## File Size & Performance

- **File Size:** ~73 KB (HTML + inline CSS/JS)
- **Load Time:** Instant in modern browsers
- **No External Dependencies:** Works offline once downloaded
- **Browser Compatibility:** Chrome, Firefox, Safari, Edge (all modern versions)

---

**Tip:** Bookmark the dashboard HTML file for quick access to your portfolio status at any time!
