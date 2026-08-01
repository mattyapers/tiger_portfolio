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


def _macro_split(text):
    """
    Split a MACRO_REGIME string into a short headline + fuller detail.

    MACRO_REGIME values are hand-written prose (e.g. '3.50-3.75% (held since
    Dec 2025 cut); Jul 29 FOMC decision tomorrow') rather than clean numbers —
    split on the first ';' or ',' so the card shows a short value with the
    rest as a sub-line, same visual pattern the old numeric cards used.
    """
    text = str(text)
    for delim in [';', ',']:
        if delim in text:
            head, rest = text.split(delim, 1)
            return head.strip(), rest.strip()
    return text.strip(), ""


def build_macro_cards(settings):
    """
    Build Macro Monitor card data straight from settings.MACRO_REGIME —
    the same dict the Excel Dashboard sheet and the Stage 0/1/2 review
    cycle (see prompts/) maintain. This used to be a separate FRED/yfinance
    fetch that silently fell back to hardcoded demo numbers (Fed Funds
    5.25%, etc.) whenever FRED_API_KEY wasn't set — which it never was —
    so the Macro Monitor contradicted the actual tracked regime. Reading
    MACRO_REGIME directly means there's only one source of truth for
    macro data across Excel, this dashboard, and the review prompts.
    """
    regime = getattr(settings, 'MACRO_REGIME', {})

    items = [("Quadrant", f"{regime.get('quadrant', 'N/A')} ({regime.get('confidence', '?')} confidence)",
              regime.get('regime_label', ''))]

    for key, label in [
        ('fed_funds_rate', 'Fed Funds Rate'),
        ('fed_balance_sheet', 'Fed Balance Sheet'),
        ('pce_headline', 'PCE (Headline)'),
        ('pce_core', 'PCE (Core)'),
        ('cpi_latest', 'CPI'),
        ('yield_curve', 'Yield Curve'),
        ('vix', 'VIX'),
        ('brent', 'Brent Crude'),
        ('fedwatch_next_meeting', 'FedWatch (Next Meeting)'),
        ('hormuz_status', 'Hormuz Status'),
        ('tariff_section_122', 'Tariff Sec 122'),
        ('mas_stance', 'MAS Stance'),
    ]:
        head, detail = _macro_split(regime.get(key, 'N/A'))
        items.append((label, head, detail))

    return items, regime.get('as_of_date', 'N/A')


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
            "forward_pe": holding.get("forward_pe"),
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
    total_realized_pnl = sum(h.get("realized_pnl", 0) or 0 for h in holdings)

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
        "total_realized_pnl": round(total_realized_pnl, 2),
        "num_holdings": len(holdings),
        "core_pct": round(core_pct, 1),
        "coreplus_pct": round(coreplus_pct, 1),
        "satellite_pct": round(satellite_pct, 1),
        "core_value": round(core_value, 2),
        "coreplus_value": round(coreplus_value, 2),
        "satellite_value": round(satellite_value, 2),
    }


def _sector_of(holding):
    """
    GICS sector for a holding. Prefers the value already captured in the
    snapshot (extract.py saves it per-position now) to avoid a redundant
    yfinance call; falls back to a live lookup for snapshots saved before
    that field existed.
    """
    sector = holding.get("sector")
    if sector:
        return sector
    try:
        return yf.Ticker(holding["symbol"]).info.get("sector") or "Unknown"
    except Exception:
        return "Unknown"


def _country_of(holding):
    """
    Listing-exchange geography for a holding: where the instrument trades
    (e.g. a US-listed ADR is 'United States' regardless of where the
    underlying business is headquartered), not a revenue look-through.
    Same snapshot-first, live-fallback pattern as _sector_of() — falls back
    to a live yfinance lookup only for snapshots saved before this field
    existed.
    """
    country = holding.get("country")
    if country:
        return country
    try:
        from modules.extract import _listing_country
        return _listing_country(yf.Ticker(holding["symbol"]).info or {}) or "Unknown"
    except Exception:
        return "Unknown"


def _group_by(holdings, key_fn, total):
    """Group holdings' market value by an arbitrary key function, ranked descending."""
    groups = {}
    for h in holdings:
        mv = h["shares"] * h["latest_price"]
        key = key_fn(h) or "Unknown"
        g = groups.setdefault(key, {"value": 0.0, "members": []})
        g["value"] += mv
        g["members"].append(h["symbol"])
    ranked = sorted(groups.items(), key=lambda kv: -kv[1]["value"])
    labels = [k for k, _ in ranked]
    values = [round(v["value"] / total * 100, 1) if total > 0 else 0 for _, v in ranked]
    members = [v["members"] for _, v in ranked]
    return labels, values, members


def calculate_allocation_chart(holdings, settings):
    """
    Build the main allocation doughnut chart — by individual ticker, for
    both books. Sector concentration has its own dedicated Exposure by
    Sector chart (calculate_exposure_charts()), so this one doesn't need
    to duplicate that view for the Satellite book anymore.
    """
    total = sum(h["shares"] * h["latest_price"] for h in holdings)
    ranked = sorted(holdings, key=lambda h: -(h["shares"] * h["latest_price"]))
    labels = [h["symbol"] for h in ranked]
    values = [round((h["shares"] * h["latest_price"]) / total * 100, 1) if total > 0 else 0 for h in ranked]
    members = [[] for _ in ranked]
    chart_title = "Allocation by Holding"

    return labels, values, chart_title, members


def calculate_exposure_charts(holdings):
    """
    Build Sector Exposure and Geography Exposure doughnut charts — shown on
    both books, independent of the main allocation chart above. Geography is
    a simple proxy: primary listing country (yfinance 'country' field), not
    a look-through of where the underlying business earns revenue.
    """
    total = sum(h["shares"] * h["latest_price"] for h in holdings)
    sector_labels, sector_values, sector_members = _group_by(holdings, _sector_of, total)
    geo_labels, geo_values, geo_members = _group_by(holdings, _country_of, total)
    return {
        "sector": (sector_labels, sector_values, sector_members),
        "geography": (geo_labels, geo_values, geo_members),
    }


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
    macro_items, macro_as_of = build_macro_cards(settings)
    chart_labels, chart_values, chart_title, chart_members = calculate_allocation_chart(holdings, settings)
    exposure = calculate_exposure_charts(holdings)
    sector_labels, sector_values, sector_members = exposure["sector"]
    geo_labels, geo_values, geo_members = exposure["geography"]

    # Stock Deep-Dive Cards: group by sector for the Satellite book (reuses the
    # sector exposure groupings computed above — no extra yfinance calls).
    # Core/Core-Plus book has no sector concept here, cards stay in order.
    is_satellite_book = 'Satellite' in settings.TIER_TARGETS
    if is_satellite_book:
        symbol_to_sector = {}
        for sector, members in zip(sector_labels, sector_members):
            for sym in members:
                symbol_to_sector[sym] = sector
        sector_rank = {sector: i for i, sector in enumerate(sector_labels)}
        holding_values = {h["symbol"]: h["shares"] * h["latest_price"] for h in holdings}
        card_holdings = sorted(
            holdings,
            key=lambda h: (sector_rank.get(symbol_to_sector.get(h["symbol"]), 999), -holding_values[h["symbol"]])
        )
    else:
        symbol_to_sector = {}
        card_holdings = holdings

    # Only render a tier card for tiers this book actually has (e.g. Satellite
    # book has no Core/Core-Plus tier — showing a $0 card for it is noise).
    tier_card_defs = [
        ('Core', 'core_pct', 'core_value'),
        ('Core-Plus', 'coreplus_pct', 'coreplus_value'),
        ('Satellite', 'satellite_pct', 'satellite_value'),
    ]
    tier_cards_html = ''.join(
        f'''<div class="metric-card">
                            <div class="metric-label">{label} ({portfolio[pct_key]:.0f}%)</div>
                            <div class="metric-value">${portfolio[val_key]:,.0f}</div>
                        </div>
                        '''
        for label, pct_key, val_key in tier_card_defs if label in settings.TIER_TARGETS
    )
    
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
        .info-tip {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 14px;
            height: 14px;
            border-radius: 50%;
            background: #1f77b4;
            color: #fff;
            font-size: 10px;
            font-weight: bold;
            font-style: normal;
            text-transform: none;
            cursor: help;
            margin-left: 5px;
            position: relative;
            vertical-align: middle;
        }}
        .info-tip::after {{
            content: attr(data-tip);
            display: none;
            position: absolute;
            bottom: 130%;
            left: 50%;
            transform: translateX(-50%);
            background: #222;
            color: #fff;
            padding: 8px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: normal;
            white-space: normal;
            width: 260px;
            z-index: 100;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            line-height: 1.4;
        }}
        .info-tip:hover::after {{
            display: block;
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
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 15px;
        }}
        .sector-divider {{
            grid-column: 1 / -1;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #666;
            padding-bottom: 6px;
            margin-top: 10px;
            border-bottom: 2px solid #1f77b4;
        }}
        .sector-divider:first-child {{
            margin-top: 0;
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
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 15px;
        }}
        .macro-card {{
            background: #f9f9f9;
            padding: 15px;
            border-radius: 6px;
            text-align: left;
            border: 1px solid #e0e0e0;
        }}
        .macro-card .label {{
            font-size: 11px;
            color: #666;
            font-weight: 600;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}
        .macro-card .value {{
            font-size: 14px;
            font-weight: 600;
            color: #333;
            line-height: 1.3;
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

            <h3 style="font-size: 13px; color: #666; text-transform: uppercase; margin-bottom: 10px;">Absolute</h3>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Total Equity</div>
                    <div class="metric-value">${portfolio['total_equity']:,.0f}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Account Cash (shared)<span class="info-tip" data-tip="This is the whole Tiger account's cash balance, not attributable to this book specifically. Both Core/Core-Plus and Satellite share one brokerage account and one cash pool -- there is no per-book cash split, so this figure is identical on both dashboards.">i</span></div>
                    <div class="metric-value">${portfolio['cash']:,.0f}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Unrealized P&L<span class="info-tip" data-tip="Market Value - Cost Basis on currently open positions in this book. Paper gain/loss only -- reverses if the price moves back before you sell.">i</span></div>
                    <div class="metric-value {'positive' if portfolio['total_pnl'] >= 0 else 'negative'}">${portfolio['total_pnl']:,.0f}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Realized P&L<span class="info-tip" data-tip="Cumulative gain/loss locked in on positions already closed or partially closed in this book, as reported by Tiger. A separate dimension from Unrealized P&amp;L above -- this money is booked and can't reverse.">i</span></div>
                    <div class="metric-value {'positive' if portfolio['total_realized_pnl'] >= 0 else 'negative'}">${portfolio['total_realized_pnl']:,.0f}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Holdings</div>
                    <div class="metric-value">{portfolio['num_holdings']}</div>
                </div>
            </div>

            <h3 style="font-size: 13px; color: #666; text-transform: uppercase; margin: 20px 0 10px;">Metrics</h3>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Return on Cost %<span class="info-tip" data-tip="Unrealized P&amp;L / Total Cost Basis x 100. Cost Basis = sum(shares x avg_cost) across this book's holdings only. This is a simple aggregate return on cost, NOT time-weighted (TWR) or money-weighted (XIRR/IRR) -- it doesn't account for when each tranche was bought, and excludes dividends received and realized gains/losses. Since-inception/YTD/monthly TWR figures require a NAV history and will populate here once enough snapshots have accumulated (see output/nav_history*.json).">i</span></div>
                    <div class="metric-value {'positive' if portfolio['total_pnl_pct'] >= 0 else 'negative'}">{portfolio['total_pnl_pct']:.2f}%</div>
                </div>
                {tier_cards_html}
            </div>

            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 30px; align-items: start; margin-top: 20px;">
                <div>
                    <h3 style="font-size: 14px; margin-bottom: 15px;">{chart_title}</h3>
                    <div class="allocation-chart">
                        <canvas id="allocationChart"></canvas>
                    </div>
                </div>
                <div>
                    <h3 style="font-size: 14px; margin-bottom: 15px;">Exposure by Sector</h3>
                    <div class="allocation-chart">
                        <canvas id="sectorExposureChart"></canvas>
                    </div>
                </div>
                <div>
                    <h3 style="font-size: 14px; margin-bottom: 15px;">Exposure by Geography<span class="info-tip" data-tip="Based on the exchange the instrument is listed/bought on -- e.g. a stock bought on a US exchange counts as United States exposure, even if the underlying company is headquartered elsewhere (ADRs, foreign-domiciled listings). Not a look-through of where the business actually earns its revenue.">i</span></h3>
                    <div class="allocation-chart">
                        <canvas id="geoExposureChart"></canvas>
                    </div>
                </div>
            </div>
        </div>

        <!-- SECTION 2: STOCK DEEP-DIVE CARDS -->
        <div class="section">
            <h2>Stock Deep-Dive Cards</h2>
            <div class="holdings-grid">
"""
    
    # Add holding cards — combines valuation + technical snapshot in one card
    # per symbol, so everything about a position is visible without jumping
    # between sections. Filtered to this book's TICKER_TIERS (see
    # calculate_portfolio_overview).
    last_sector = None
    for holding in card_holdings:
        symbol = holding["symbol"]
        val = valuation.get(symbol, {})
        tech = technical.get(symbol, {})
        gain_loss_pct = val.get('gain_loss_pct', 0)
        bar_width = max(0, min(100, abs(gain_loss_pct)))
        bar_color = '#27ae60' if gain_loss_pct >= 0 else '#e74c3c'

        sector = symbol_to_sector.get(symbol)
        if is_satellite_book and sector != last_sector:
            html += f"""
                <div class="sector-divider">{sector}</div>
"""
            last_sector = sector

        # Golden cross (50D > 200D, bullish trend) / death cross (bearish) —
        # only meaningful once both MAs exist.
        ma_50 = tech.get('ma_50')
        ma_200 = tech.get('ma_200')
        if ma_50 is not None and ma_200 is not None:
            if ma_50 > ma_200:
                cross_label, cross_class = 'Golden Cross (bullish)', 'positive'
            else:
                cross_label, cross_class = 'Death Cross (bearish)', 'negative'
            cross_tip = 'data-tip="50D MA above 200D MA = shorter-term trend running above the longer-term trend (golden cross, bullish). Below = death cross, bearish. Distance from each MA (below) shows how extended price is versus that trend line."'
        else:
            cross_label, cross_class, cross_tip = 'N/A', '', ''

        rsi = tech.get('rsi')
        if rsi is None:
            rsi_class, rsi_label = 'neutral', 'N/A'
        elif rsi > 70:
            rsi_class, rsi_label = 'overbought', 'Overbought'
        elif rsi < 30:
            rsi_class, rsi_label = 'oversold', 'Oversold'
        else:
            rsi_class, rsi_label = 'neutral', 'Neutral'

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
                        <label>P/E (Fwd):</label>
                        <span>{val.get('forward_pe', 'N/A')}</span>
                    </div>
                    <div class="holding-stat">
                        <label>Gain/Loss:</label>
                        <span class="{'positive' if gain_loss_pct >= 0 else 'negative'}">{gain_loss_pct:.1f}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {bar_width}%; background: {bar_color};"></div>
                    </div>
                    <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 10px 0;">
                    <div class="holding-stat">
                        <label>52W High:</label>
                        <span>{'$' + format(tech['high_52w'], '.2f') if 'high_52w' in tech else 'N/A'}</span>
                    </div>
                    <div class="holding-stat">
                        <label>52W Low:</label>
                        <span>{'$' + format(tech['low_52w'], '.2f') if 'low_52w' in tech else 'N/A'}</span>
                    </div>
                    <div class="holding-stat">
                        <label>From 52W High:</label>
                        <span style="color: #666;">{format(tech['dist_from_high'], '.1f') + '%' if 'dist_from_high' in tech else 'N/A'}</span>
                    </div>
                    <div class="holding-stat">
                        <label>From 52W Low:</label>
                        <span style="color: #27ae60;">{format(tech['dist_from_low'], '.1f') + '%' if 'dist_from_low' in tech else 'N/A'}</span>
                    </div>
                    <div class="holding-stat">
                        <label>50D MA / 200D MA:</label>
                        <span>{('$' + format(ma_50, '.2f') + ' / $' + format(ma_200, '.2f')) if ma_50 is not None and ma_200 is not None else 'N/A'}</span>
                    </div>
                    <div class="holding-stat">
                        <label>vs 50D / vs 200D:</label>
                        <span>{(format(tech['ma_50_pct'], '.1f') + '% / ' + format(tech['ma_200_pct'], '.1f') + '%') if 'ma_50_pct' in tech else 'N/A'}</span>
                    </div>
                    <div class="holding-stat">
                        <label>Trend:<span class="info-tip" {cross_tip}>i</span></label>
                        <span class="{cross_class}">{cross_label}</span>
                    </div>
                    <div class="rsi {rsi_class}">
                        RSI (14): {format(rsi, '.1f') if rsi is not None else 'N/A'} — {rsi_label}
                    </div>
                </div>
"""

    html += f"""
            </div>
        </div>

        <!-- SECTION 3: MACRO MONITOR -->
        <div class="section">
            <h2>Macro Monitor</h2>
            <p style="font-size: 12px; color: #666; margin-top: -10px; margin-bottom: 15px;">
                Source: MACRO_REGIME (config/settings*.py) — as of {macro_as_of}. Updated via the Stage 0/1/2 review cycle, not a live feed.
            </p>
            <div class="macro-grid">
"""

    for label, value, desc in macro_items:
        html += f"""
                <div class="macro-card">
                    <div class="label">{label}</div>
                    <div class="value">{value}</div>
                    <div style="font-size: 11px; color: #555; margin-top: 5px; line-height: 1.4;">{desc}</div>
                </div>
"""

    html += """
            </div>
        </div>

        <!-- APPENDIX & DISCLAIMER -->
        <div class="section">
            <div class="appendix">
                <h4>📊 Data Sources & Refresh Cadence</h4>
                <p><strong>Holdings & Pricing:</strong> Yahoo Finance (yfinance) — Real-time during market hours</p>
                <p><strong>Macro/Regime Data:</strong> MACRO_REGIME dict in config/settings.py or settings_satellite.py — manually refreshed each cycle via the Stage 0/1/2 review workflow (see prompts/), not a live feed. See the "as of" date above the Macro Monitor section.</p>
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
        const allocationMembers = {chart_members!r};
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
                    }},
                    tooltip: {{
                        callbacks: {{
                            label: function(context) {{
                                return context.label + ': ' + context.parsed + '%';
                            }},
                            afterLabel: function(context) {{
                                const members = allocationMembers[context.dataIndex];
                                if (members && members.length) {{
                                    return 'Stocks: ' + members.join(', ');
                                }}
                                return '';
                            }}
                        }}
                    }}
                }}
            }}
        }});

        // Sector Exposure Chart (Doughnut)
        const sectorCtx = document.getElementById('sectorExposureChart').getContext('2d');
        new Chart(sectorCtx, {{
            type: 'doughnut',
            data: {{
                labels: {sector_labels!r},
                datasets: [{{
                    data: {sector_values!r},
                    backgroundColor: ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf', '#aec7e8', '#ffbb78', '#98df8a', '#ff9896'],
                    borderColor: '#fff',
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ position: 'bottom', labels: {{ font: {{ size: 11 }} }} }},
                    tooltip: {{
                        callbacks: {{
                            label: function(context) {{ return context.label + ': ' + context.parsed + '%'; }},
                            afterLabel: function(context) {{
                                const members = {sector_members!r}[context.dataIndex];
                                return members && members.length ? 'Stocks: ' + members.join(', ') : '';
                            }}
                        }}
                    }}
                }}
            }}
        }});

        // Geography Exposure Chart (Doughnut)
        const geoCtx = document.getElementById('geoExposureChart').getContext('2d');
        new Chart(geoCtx, {{
            type: 'doughnut',
            data: {{
                labels: {geo_labels!r},
                datasets: [{{
                    data: {geo_values!r},
                    backgroundColor: ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf', '#aec7e8', '#ffbb78', '#98df8a', '#ff9896'],
                    borderColor: '#fff',
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ position: 'bottom', labels: {{ font: {{ size: 11 }} }} }},
                    tooltip: {{
                        callbacks: {{
                            label: function(context) {{ return context.label + ': ' + context.parsed + '%'; }},
                            afterLabel: function(context) {{
                                const members = {geo_members!r}[context.dataIndex];
                                return members && members.length ? 'Stocks: ' + members.join(', ') : '';
                            }}
                        }}
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
