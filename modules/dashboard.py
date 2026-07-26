"""
Portfolio Dashboard Generator
Creates a self-contained HTML dashboard with Portfolio Overview, Stock Cards,
Macro Monitor, and Technical Snapshot using free CDN charting libraries.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import yfinance as yf

# For macro data (FRED API) - use fredapi if installed, else fallback to demo data
try:
    from fredapi import Fred
    FRED_AVAILABLE = True
except ImportError:
    FRED_AVAILABLE = False


def load_snapshot(snapshot_path="output/latest_snapshot.json"):
    """Load portfolio snapshot from JSON."""
    with open(snapshot_path, "r") as f:
        return json.load(f)


def fetch_technical_data(symbols, lookback_days=365):
    """
    Fetch technical indicators for holdings.
    Returns: dict with RSI, 52-week high/low, 50/200-day MAs.
    """
    technical_data = {}
    
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=f"{lookback_days}d")
            
            if len(hist) < 50:
                continue
            
            close = hist["Close"]
            
            # 52-week high/low
            high_52w = close.tail(252).max() if len(close) >= 252 else close.max()
            low_52w = close.tail(252).min() if len(close) >= 252 else close.min()
            current = close.iloc[-1]
            
            # Moving averages
            ma_50 = close.tail(50).mean()
            ma_200 = close.tail(200).mean() if len(close) >= 200 else close.mean()
            
            # RSI (14-day)
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss if loss.iloc[-1] != 0 else 0
            rsi = 100 - (100 / (1 + rs.iloc[-1]))
            
            # Distance from 52-week high/low (%)
            dist_from_high = ((high_52w - current) / current * 100)
            dist_from_low = ((current - low_52w) / low_52w * 100)
            
            # Position relative to MAs
            ma_50_pct = ((current - ma_50) / ma_50 * 100)
            ma_200_pct = ((current - ma_200) / ma_200 * 100)
            
            technical_data[symbol] = {
                "high_52w": round(high_52w, 2),
                "low_52w": round(low_52w, 2),
                "current": round(current, 2),
                "dist_from_high": round(dist_from_high, 1),
                "dist_from_low": round(dist_from_low, 1),
                "ma_50": round(ma_50, 2),
                "ma_200": round(ma_200, 2),
                "ma_50_pct": round(ma_50_pct, 1),
                "ma_200_pct": round(ma_200_pct, 1),
                "rsi": round(rsi, 1),
            }
        except Exception as e:
            print(f"Error fetching technical data for {symbol}: {e}")
            continue
    
    return technical_data


def fetch_macro_data():
    """
    Fetch macro indicators. Returns dict with key macro metrics.
    Falls back to demonstration data if FRED API unavailable.
    """
    macro = {}
    
    if FRED_AVAILABLE:
        try:
            # Requires FRED API key in environment variable
            fred_key = os.getenv("FRED_API_KEY")
            if fred_key:
                fred = Fred(api_key=fred_key)
                macro = {
                    "cpi": round(fred.get_series("CPIAUCSL").iloc[-1], 2),
                    "pce": round(fred.get_series("PCEPI").iloc[-1], 2),
                    "unemployment": round(fred.get_series("UNRATE").iloc[-1], 2),
                    "fed_funds": round(fred.get_series("FEDFUNDS").iloc[-1], 3),
                    "real_gdp_growth": round(fred.get_series("A191RL1Q225SBEA").iloc[-1], 2),
                }
        except Exception as e:
            print(f"FRED API error: {e}")
    
    # Fetch Treasury yields from yfinance
    try:
        yields = yf.Tickers("^TNX ^FVX").tickers
        tnx = yf.Ticker("^TNX").info.get("currentPrice", 4.2)
        fvx = yf.Ticker("^FVX").info.get("currentPrice", 3.9)
        
        macro["yield_10y"] = round(tnx, 2)
        macro["yield_2y"] = round(fvx, 2)
        macro["yield_curve"] = round(tnx - fvx, 2)
    except Exception as e:
        print(f"Treasury yields error: {e}")
        macro["yield_10y"] = 4.2
        macro["yield_2y"] = 3.9
        macro["yield_curve"] = 0.3
    
    # Fallback demo data if incomplete
    defaults = {
        "cpi": 315.5,
        "pce": 308.2,
        "unemployment": 4.1,
        "fed_funds": 5.25,
        "real_gdp_growth": 2.1,
        "yield_10y": 4.2,
        "yield_2y": 3.9,
        "yield_curve": 0.3,
        "dxy": 103.2,
    }
    
    for key in defaults:
        if key not in macro:
            macro[key] = defaults[key]
    
    return macro


def calculate_valuation_metrics(snapshot, settings):
    """
    Calculate valuation metrics for stock cards.
    For now, uses P/E from snapshot. In full impl, would fetch P/S, P/B, etc.

    Filtered to this book's TICKER_TIERS — see calculate_portfolio_overview().
    """
    tier_map = settings.TICKER_TIERS
    holdings = [h for h in snapshot.get("holdings", []) if h["symbol"] in tier_map]
    valuation = {}

    for holding in holdings:
        symbol = holding["symbol"]
        latest_price = holding["latest_price"]
        avg_cost = holding["avg_cost"]
        pe_ttm = holding.get("pe_ttm")
        
        # Basic metrics from snapshot
        valuation[symbol] = {
            "pe_ttm": pe_ttm,
            "price_to_cost": round(latest_price / avg_cost, 2) if avg_cost > 0 else 1.0,
            "gain_loss_pct": round((latest_price - avg_cost) / avg_cost * 100, 1),
        }
    
    return valuation


def calculate_portfolio_overview(snapshot, settings):
    """
    Calculate portfolio-level metrics — filtered to this book's TICKER_TIERS.

    The raw snapshot's "holdings" and "account.total_equity" cover the whole
    Tiger account (both books combined, since they share one account). Mirror
    transform.py's classify_tiers(): drop any symbol not in this book's
    TICKER_TIERS before computing totals, or the satellite dashboard shows
    Core/Core-Plus value baked into its total (and vice versa).
    """
    account = snapshot.get("account", {})
    all_holdings = snapshot.get("holdings", [])
    tier_map = settings.TICKER_TIERS
    holdings = [h for h in all_holdings if h["symbol"] in tier_map]

    market_values = [h["shares"] * h["latest_price"] for h in holdings]
    cost_bases = [h["shares"] * h["avg_cost"] for h in holdings]

    total_equity = sum(market_values)
    total_cost = sum(cost_bases)
    total_pnl = total_equity - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    def tier_value(*tiers):
        return sum(mv for h, mv in zip(holdings, market_values) if tier_map[h["symbol"]] in tiers)

    core_value = tier_value("Core", "Core-Bond")
    coreplus_value = tier_value("Core-Plus")
    satellite_value = tier_value("Satellite")

    core_pct = (core_value / total_equity * 100) if total_equity > 0 else 0
    coreplus_pct = (coreplus_value / total_equity * 100) if total_equity > 0 else 0
    satellite_pct = (satellite_value / total_equity * 100) if total_equity > 0 else 0

    return {
        "total_equity": round(total_equity, 2),
        "cash": round(account.get("cash_balance", 0), 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "num_holdings": len(holdings),
        "core_pct": round(core_pct, 1),
        "coreplus_pct": round(coreplus_pct, 1),
        "satellite_pct": round(satellite_pct, 1),
        "core_value": round(core_value, 2),
        "coreplus_value": round(coreplus_value, 2),
        "satellite_value": round(satellite_value, 2),
    }


def calculate_allocation_chart(holdings, settings):
    """
    Build the doughnut-chart breakdown.

    Core/Core-Plus book: by individual ticker (no Satellite tier there, so a
    tier pie is just "Core" vs "Core-Plus" — individual holdings are more useful).
    Satellite book: by GICS sector (yfinance) — a per-ticker pie is too granular
    for a 100%-Satellite book where the interesting question is sector concentration.
    """
    total = sum(h["shares"] * h["latest_price"] for h in holdings)
    is_satellite_book = 'Satellite' in settings.TIER_TARGETS

    if is_satellite_book:
        sector_totals = {}
        for h in holdings:
            mv = h["shares"] * h["latest_price"]
            try:
                sector = yf.Ticker(h["symbol"]).info.get("sector") or "Unknown"
            except Exception:
                sector = "Unknown"
            sector_totals[sector] = sector_totals.get(sector, 0) + mv
        ranked = sorted(sector_totals.items(), key=lambda kv: -kv[1])
        labels = [k for k, _ in ranked]
        values = [round(v / total * 100, 1) if total > 0 else 0 for _, v in ranked]
        chart_title = "Allocation by Sector"
    else:
        ranked = sorted(holdings, key=lambda h: -(h["shares"] * h["latest_price"]))
        labels = [h["symbol"] for h in ranked]
        values = [round((h["shares"] * h["latest_price"]) / total * 100, 1) if total > 0 else 0 for h in ranked]
        chart_title = "Allocation by Holding"

    return labels, values, chart_title


def generate_html_dashboard(settings, snapshot_path="output/latest_snapshot.json", output_path="output/dashboard.html"):
    """Generate the self-contained HTML dashboard."""

    # Load data
    snapshot = load_snapshot(snapshot_path)
    portfolio = calculate_portfolio_overview(snapshot, settings)
    valuation = calculate_valuation_metrics(snapshot, settings)

    tier_map = settings.TICKER_TIERS
    holdings = [h for h in snapshot.get("holdings", []) if h["symbol"] in tier_map]
    symbols = [h["symbol"] for h in holdings]
    technical = fetch_technical_data(symbols)
    macro = fetch_macro_data()
    chart_labels, chart_values, chart_title = calculate_allocation_chart(holdings, settings)
    
    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Portfolio Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        h1 {{
            font-size: 28px;
            margin-bottom: 5px;
        }}
        .timestamp {{
            color: #666;
            font-size: 12px;
        }}
        .section {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            font-size: 20px;
            margin-bottom: 20px;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 10px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .metric-card {{
            background: #f9f9f9;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #1f77b4;
        }}
        .metric-label {{
            font-size: 12px;
            color: #999;
            text-transform: uppercase;
            margin-bottom: 5px;
        }}
        .metric-value {{
            font-size: 20px;
            font-weight: 600;
            color: #333;
        }}
        .metric-value.positive {{
            color: #27ae60;
        }}
        .metric-value.negative {{
            color: #e74c3c;
        }}
        .allocation-chart {{
            max-width: 400px;
            margin: 0 auto 30px;
        }}
        .holdings-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 15px;
        }}
        .holding-card {{
            background: #f9f9f9;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #e0e0e0;
        }}
        .holding-card h3 {{
            font-size: 16px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .holding-card .price {{
            font-weight: 600;
            color: #1f77b4;
        }}
        .holding-stat {{
            display: flex;
            justify-content: space-between;
            padding: 5px 0;
            font-size: 12px;
        }}
        .holding-stat label {{
            color: #999;
        }}
        .progress-bar {{
            width: 100%;
            height: 6px;
            background: #e0e0e0;
            border-radius: 3px;
            overflow: hidden;
            margin-top: 8px;
        }}
        .progress-fill {{
            height: 100%;
            background: #1f77b4;
            transition: width 0.3s;
        }}
        .macro-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }}
        .macro-card {{
            background: #f9f9f9;
            padding: 15px;
            border-radius: 6px;
            text-align: center;
            border: 1px solid #e0e0e0;
        }}
        .macro-card .label {{
            font-size: 11px;
            color: #999;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}
        .macro-card .value {{
            font-size: 18px;
            font-weight: 600;
            color: #333;
        }}
        .technical-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 15px;
        }}
        .technical-card {{
            background: #f9f9f9;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #e0e0e0;
        }}
        .technical-card h4 {{
            font-size: 14px;
            margin-bottom: 10px;
            font-weight: 600;
        }}
        .technical-row {{
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            font-size: 12px;
        }}
        .technical-row .label {{
            color: #999;
        }}
        .technical-row .value {{
            font-weight: 600;
            color: #333;
        }}
        .rsi {{
            padding: 10px;
            border-radius: 4px;
            margin-top: 10px;
            font-size: 12px;
            font-weight: 600;
            text-align: center;
        }}
        .rsi.overbought {{
            background: #ffe0e0;
            color: #e74c3c;
        }}
        .rsi.neutral {{
            background: #e0f0ff;
            color: #1f77b4;
        }}
        .rsi.oversold {{
            background: #e0ffe0;
            color: #27ae60;
        }}
        .appendix {{
            background: #f9f9f9;
            padding: 15px;
            border-radius: 6px;
            font-size: 12px;
            color: #666;
            margin-top: 20px;
            border-top: 1px solid #e0e0e0;
        }}
        .appendix h4 {{
            font-size: 13px;
            margin-bottom: 8px;
            color: #333;
        }}
        .appendix p {{
            margin-bottom: 8px;
        }}
        .disclaimer {{
            background: #fffbea;
            border-left: 4px solid #f39c12;
            padding: 15px;
            border-radius: 4px;
            font-size: 12px;
            margin-top: 20px;
        }}
        .chart-container {{
            position: relative;
            height: 300px;
            margin-bottom: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Portfolio Dashboard</h1>
            <p class="timestamp">Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Data snapshot: {snapshot.get("timestamp", "N/A")}</p>
        </header>

        <!-- SECTION 1: PORTFOLIO OVERVIEW -->
        <div class="section">
            <h2>Portfolio Overview</h2>
            
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Total Equity</div>
                    <div class="metric-value">${portfolio['total_equity']:,.0f}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Cash Balance</div>
                    <div class="metric-value">${portfolio['cash']:,.0f}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Unrealized P&L</div>
                    <div class="metric-value {'positive' if portfolio['total_pnl'] >= 0 else 'negative'}">${portfolio['total_pnl']:,.0f}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Return %</div>
                    <div class="metric-value {'positive' if portfolio['total_pnl_pct'] >= 0 else 'negative'}">{portfolio['total_pnl_pct']:.2f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Holdings</div>
                    <div class="metric-value">{portfolio['num_holdings']}</div>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px; align-items: start;">
                <div>
                    <h3 style="font-size: 14px; margin-bottom: 15px;">{chart_title}</h3>
                    <div class="allocation-chart">
                        <canvas id="allocationChart"></canvas>
                    </div>
                </div>
                <div>
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <div class="metric-label">Core ({portfolio['core_pct']:.0f}%)</div>
                            <div class="metric-value">${portfolio['core_value']:,.0f}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Core-Plus ({portfolio['coreplus_pct']:.0f}%)</div>
                            <div class="metric-value">${portfolio['coreplus_value']:,.0f}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Satellite ({portfolio['satellite_pct']:.0f}%)</div>
                            <div class="metric-value">${portfolio['satellite_value']:,.0f}</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- SECTION 2: STOCK DEEP-DIVE CARDS -->
        <div class="section">
            <h2>Stock Deep-Dive Cards</h2>
            <div class="holdings-grid">
"""
    
    # Add holding cards — filtered to this book's TICKER_TIERS (see calculate_portfolio_overview)
    for holding in holdings:
        symbol = holding["symbol"]
        val = valuation.get(symbol, {})
        
        html += f"""
                <div class="holding-card">
                    <h3>
                        <span>{symbol}</span>
                        <span class="price">${holding['latest_price']:.2f}</span>
                    </h3>
                    <div class="holding-stat">
                        <label>Shares:</label>
                        <span>{holding['shares']:.4f}</span>
                    </div>
                    <div class="holding-stat">
                        <label>Avg Cost:</label>
                        <span>${holding['avg_cost']:.2f}</span>
                    </div>
                    <div class="holding-stat">
                        <label>P/E (TTM):</label>
                        <span>{val.get('pe_ttm', 'N/A')}</span>
                    </div>
                    <div class="holding-stat">
                        <label>Gain/Loss:</label>
                        <span class="{'positive' if val.get('gain_loss_pct', 0) >= 0 else 'negative'}">{val.get('gain_loss_pct', 0):.1f}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {max(0, min(100, val.get('gain_loss_pct', 0) + 50))}%"></div>
                    </div>
                </div>
"""
    
    html += """
            </div>
        </div>

        <!-- SECTION 3: MACRO MONITOR -->
        <div class="section">
            <h2>Macro Monitor</h2>
            <div class="macro-grid">
"""
    
    # Add macro cards
    macro_items = [
        ("CPI", f"{macro.get('cpi', 'N/A')}", "Consumer Price Index"),
        ("PCE", f"{macro.get('pce', 'N/A')}", "Personal Consumption Expenditures"),
        ("Unemployment", f"{macro.get('unemployment', 'N/A')}%", "Unemployment Rate"),
        ("Fed Funds", f"{macro.get('fed_funds', 'N/A')}%", "Federal Funds Rate"),
        ("GDP Growth", f"{macro.get('real_gdp_growth', 'N/A')}%", "Real GDP Growth (YoY)"),
        ("10Y Yield", f"{macro.get('yield_10y', 'N/A')}%", "10-Year Treasury"),
        ("2Y Yield", f"{macro.get('yield_2y', 'N/A')}%", "2-Year Treasury"),
        ("Yield Curve", f"{macro.get('yield_curve', 'N/A')}%", "10Y - 2Y Spread"),
        ("DXY", f"{macro.get('dxy', 'N/A')}", "USD Dollar Index"),
    ]
    
    for label, value, desc in macro_items:
        html += f"""
                <div class="macro-card">
                    <div class="label">{label}</div>
                    <div class="value">{value}</div>
                    <div style="font-size: 10px; color: #ccc; margin-top: 5px;">{desc}</div>
                </div>
"""
    
    html += """
            </div>
        </div>

        <!-- SECTION 4: TECHNICAL SNAPSHOT -->
        <div class="section">
            <h2>Technical Snapshot</h2>
            <div class="technical-grid">
"""
    
    # Add technical cards for symbols with data
    for symbol in symbols:
        if symbol in technical:
            tech = technical[symbol]
            rsi = tech.get("rsi", 50)
            
            if rsi > 70:
                rsi_class = "overbought"
                rsi_label = "Overbought"
            elif rsi < 30:
                rsi_class = "oversold"
                rsi_label = "Oversold"
            else:
                rsi_class = "neutral"
                rsi_label = "Neutral"
            
            html += f"""
                <div class="technical-card">
                    <h4>{symbol}</h4>
                    <div class="technical-row">
                        <span class="label">52W High:</span>
                        <span class="value">${tech['high_52w']:.2f}</span>
                    </div>
                    <div class="technical-row">
                        <span class="label">52W Low:</span>
                        <span class="value">${tech['low_52w']:.2f}</span>
                    </div>
                    <div class="technical-row">
                        <span class="label">From 52W High:</span>
                        <span class="value" style="color: #999;">{tech['dist_from_high']:.1f}%</span>
                    </div>
                    <div class="technical-row">
                        <span class="label">From 52W Low:</span>
                        <span class="value" style="color: #27ae60;">{tech['dist_from_low']:.1f}%</span>
                    </div>
                    <div class="technical-row">
                        <span class="label">50D MA:</span>
                        <span class="value">${tech['ma_50']:.2f}</span>
                    </div>
                    <div class="technical-row">
                        <span class="label">vs 50D MA:</span>
                        <span class="value">{tech['ma_50_pct']:.1f}%</span>
                    </div>
                    <div class="technical-row">
                        <span class="label">200D MA:</span>
                        <span class="value">${tech['ma_200']:.2f}</span>
                    </div>
                    <div class="technical-row">
                        <span class="label">vs 200D MA:</span>
                        <span class="value">{tech['ma_200_pct']:.1f}%</span>
                    </div>
                    <div class="rsi {rsi_class}">
                        RSI (14): {rsi:.1f} — {rsi_label}
                    </div>
                </div>
"""
    
    html += f"""
            </div>
        </div>

        <!-- APPENDIX & DISCLAIMER -->
        <div class="section">
            <div class="appendix">
                <h4>📊 Data Sources & Refresh Cadence</h4>
                <p><strong>Holdings & Pricing:</strong> Yahoo Finance (yfinance) — Real-time during market hours</p>
                <p><strong>Economic Indicators:</strong> Federal Reserve Economic Data (FRED API) — Daily updates</p>
                <p><strong>Treasury Yields:</strong> Yahoo Finance — Real-time</p>
                <p><strong>Technical Indicators:</strong> Calculated from 1-year historical price data (yfinance) — Daily</p>
                <p><strong>Recommended Refresh:</strong> Daily (EOD) for position tracking; Weekly for macro/technical analysis</p>
            </div>
            <div class="disclaimer">
                ⚠️ <strong>Disclaimer:</strong> This dashboard is for informational purposes only and does not constitute financial advice. All data is subject to market delays and data provider limitations. Past performance does not guarantee future results. Always consult a financial advisor before making investment decisions.
            </div>
        </div>
    </div>

    <script>
        // Allocation Chart (Doughnut)
        const allocationCtx = document.getElementById('allocationChart').getContext('2d');
        new Chart(allocationCtx, {{
            type: 'doughnut',
            data: {{
                labels: {chart_labels!r},
                datasets: [{{
                    data: {chart_values!r},
                    backgroundColor: ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf', '#aec7e8', '#ffbb78', '#98df8a', '#ff9896'],
                    borderColor: '#fff',
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom',
                        labels: {{ font: {{ size: 12 }} }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
    
    # Write to file
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"Dashboard generated: {output_path}")
    return output_path


if __name__ == "__main__":
    import sys
    if '--satellite' in sys.argv[1:]:
        from config import settings_satellite as _settings
    else:
        from config import settings as _settings
    generate_html_dashboard(
        _settings,
        snapshot_path=getattr(_settings, 'SNAPSHOT_PATH', 'output/latest_snapshot.json'),
        output_path=getattr(_settings, 'DASHBOARD_PATH', 'output/dashboard.html'),
    )
