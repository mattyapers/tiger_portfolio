"""
extract.py — Stage 1: Pull portfolio + market data.

MODES (set via command line):
  --hybrid  (default): Tiger positions + yfinance prices (RECOMMENDED)
  --offline:           Manual snapshot, no API needed
  --yf-only:           Offline shares + yfinance prices (test without Tiger)

ARCHITECTURE (Hybrid):
  Tiger API (free tier) → what you OWN: shares, avg_cost, market_value, P&L
  yfinance (free)       → what it's WORTH: latest_price, pe_ttm, dividends
  Merge + validate      → complete DataFrame for transform.py

FRACTIONAL SHARE FIX:
  Tiger sometimes reports 0.6849 shares as quantity=6849.
  Detection: if (tiger_quantity * yf_price) >> tiger_market_value, shares inflated.
  Fix: real_shares = tiger_market_value / yf_price

DEPENDENCIES:
  pip install tigeropen yfinance
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
# TIGER API — What you OWN (free tier)
# ════════════════════════════════════════════════════════════

def _connect_tiger(settings):
    from tigeropen.common.consts import Language
    from tigeropen.common.util.signature_utils import read_private_key
    from tigeropen.tiger_open_config import TigerOpenClientConfig
    from tigeropen.trade.trade_client import TradeClient
    from tigeropen.quote.quote_client import QuoteClient

    config = TigerOpenClientConfig(sandbox_debug=False)
    config.private_key = read_private_key(settings.PRIVATE_KEY_PATH)
    config.tiger_id = settings.TIGER_ID
    config.account = settings.ACCOUNT
    config.language = Language.en_US
    config.license = getattr(settings, 'LICENSE', 'TBSG')

    trade_client = TradeClient(config, logger=logger)
    quote_client = QuoteClient(config, logger=logger)
    logger.info(f"Connected to Tiger API | Account: {settings.ACCOUNT}")
    return trade_client, quote_client


def _fetch_tiger_positions(trade_client):
    """Pull positions from Tiger. Shares may need normalization."""
    positions = trade_client.get_positions()
    if not positions:
        logger.warning("No positions from Tiger API")
        return pd.DataFrame()

    rows = []
    for pos in positions:
        rows.append({
            'symbol': pos.contract.symbol,
            'tiger_shares': pos.quantity,
            'avg_cost': pos.average_cost,
            'tiger_market_value': pos.market_value,
            'unrealized_pnl': pos.unrealized_pnl,
            'realized_pnl': pos.realized_pnl,
        })

    df = pd.DataFrame(rows)
    logger.info(f"Tiger API: {len(df)} positions")
    return df


def _fetch_tiger_account(trade_client):
    """Pull account summary from Tiger."""
    try:
        assets = trade_client.get_prime_assets(base_currency='USD')
        seg = assets.segments.get('S')
        return {
            'total_equity': seg.equity_with_loan if seg else 0,
            'cash_balance': seg.cash_balance if seg else 0,
            'buying_power': seg.buying_power if seg else 0,
            'unrealized_pnl': seg.unrealized_pl if seg else 0,
            'timestamp': datetime.now().isoformat(),
        }
    except Exception as e:
        logger.warning(f"Prime assets failed: {e}")
        try:
            assets_list = trade_client.get_assets(segment=True, market_value=True)
            if assets_list:
                acct = assets_list[0]
                return {
                    'total_equity': getattr(acct.summary, 'net_liquidation', 0) or 0,
                    'cash_balance': getattr(acct.summary, 'cash', 0) or 0,
                    'buying_power': getattr(acct.summary, 'buying_power', 0) or 0,
                    'unrealized_pnl': getattr(acct.summary, 'unrealized_pnl', 0) or 0,
                    'timestamp': datetime.now().isoformat(),
                }
        except Exception as e2:
            logger.error(f"Account summary failed: {e2}")

    return {'total_equity': 0, 'cash_balance': 0, 'buying_power': 0,
            'unrealized_pnl': 0, 'timestamp': datetime.now().isoformat()}


# ════════════════════════════════════════════════════════════
# YFINANCE — What it's WORTH (free, no API key)
# ════════════════════════════════════════════════════════════

def _fetch_yfinance_data(symbols):
    """
    Pull prices + fundamentals from Yahoo Finance (free).

    Returns DataFrame: symbol, latest_price, pe_ttm, forward_pe,
                       dividend_yield, market_cap, 52wk high/low, sector
    """
    import yfinance as yf

    rows = []

    # Batch price download (fast, single HTTP call)
    latest_prices = {}
    try:
        price_data = yf.download(symbols, period='5d', progress=False)
        if not price_data.empty and 'Close' in price_data.columns:
            last_row = price_data['Close'].iloc[-1]
            if isinstance(last_row, pd.Series):
                latest_prices = last_row.to_dict()
            else:
                latest_prices = {symbols[0]: last_row}
    except Exception as e:
        logger.warning(f"yfinance batch download failed: {e}")

    # Individual ticker info (slower but gets fundamentals)
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            info = ticker.info or {}

            price = (
                info.get('currentPrice')
                or info.get('regularMarketPrice')
                or info.get('previousClose')
                or latest_prices.get(sym)
            )

            rows.append({
                'symbol': sym,
                'latest_price': float(price) if price else None,
                'pe_ttm': info.get('trailingPE'),
                'forward_pe': info.get('forwardPE'),
                'dividend_yield': info.get('dividendYield'),
                'market_cap': info.get('marketCap'),
                'fifty_two_wk_high': info.get('fiftyTwoWeekHigh'),
                'fifty_two_wk_low': info.get('fiftyTwoWeekLow'),
                'sector': info.get('sector'),
            })

        except Exception as e:
            price = latest_prices.get(sym)
            rows.append({
                'symbol': sym,
                'latest_price': float(price) if price else None,
                'pe_ttm': None, 'forward_pe': None,
                'dividend_yield': None, 'market_cap': None,
                'fifty_two_wk_high': None, 'fifty_two_wk_low': None,
                'sector': None,
            })
            logger.warning(f"  {sym}: info failed ({type(e).__name__}), batch price={'${:.2f}'.format(price) if price else 'N/A'}")

    df = pd.DataFrame(rows)
    valid = df['latest_price'].notna().sum()
    logger.info(f"yfinance: prices for {valid}/{len(symbols)} symbols")
    return df


# ════════════════════════════════════════════════════════════
# MERGE + VALIDATE
# ════════════════════════════════════════════════════════════

def _merge_and_fix(tiger_df, yf_df, settings):
    """
    Merge Tiger positions with yfinance data + fix fractional shares.

    Detects inflated share counts by comparing:
      tiger_shares * yf_price  vs  tiger_market_value
    If off by >5x, assumes shares are inflated and recalculates.
    """
    df = tiger_df.merge(yf_df[['symbol', 'latest_price', 'pe_ttm', 'forward_pe',
                                'dividend_yield', 'fifty_two_wk_high', 'fifty_two_wk_low']],
                        on='symbol', how='left')

    # Detect inflated share counts
    has_price = df['latest_price'].notna() & (df['latest_price'] > 0)
    expected_mv = df['tiger_shares'] * df['latest_price']
    inflated = has_price & (expected_mv > df['tiger_market_value'].abs() * 5)

    if inflated.sum() > 0:
        logger.warning(f"Fixing {inflated.sum()} inflated share counts:")
        for idx in df[inflated].index:
            sym = df.loc[idx, 'symbol']
            old = df.loc[idx, 'tiger_shares']
            new = df.loc[idx, 'tiger_market_value'] / df.loc[idx, 'latest_price']
            logger.info(f"  {sym}: {old:.0f} → {new:.4f}")

    # Final shares: fixed if inflated, otherwise trust Tiger
    df['shares'] = np.where(
        inflated,
        df['tiger_market_value'] / df['latest_price'],
        df['tiger_shares']
    )

    # Fallback for symbols without yfinance price
    no_price = df['latest_price'].isna() | (df['latest_price'] == 0)
    if no_price.any():
        df.loc[no_price, 'latest_price'] = np.where(
            df.loc[no_price, 'shares'] > 0,
            df.loc[no_price, 'tiger_market_value'] / df.loc[no_price, 'tiger_shares'],
            0
        )
        df.loc[no_price, 'shares'] = df.loc[no_price, 'tiger_shares']
        logger.warning(f"No yfinance price for: {df.loc[no_price, 'symbol'].tolist()}")

    # Derived fields
    df['market_value'] = df['shares'] * df['latest_price']
    df['cost_basis'] = df['shares'] * df['avg_cost']
    df['unrealized_pnl'] = df['market_value'] - df['cost_basis']

    df = df.drop(columns=['tiger_shares', 'tiger_market_value'], errors='ignore')
    return df


# ════════════════════════════════════════════════════════════
# EXTRACT MODES
# ════════════════════════════════════════════════════════════

def extract_hybrid(settings):
    """
    RECOMMENDED: Tiger positions + yfinance prices.
    Fixes fractional shares automatically. No paid subscription needed.
    """
    logger.info("=" * 50)
    logger.info("HYBRID MODE: Tiger API + yfinance")
    logger.info("=" * 50)

    trade_client, _ = _connect_tiger(settings)
    tiger_df = _fetch_tiger_positions(trade_client)
    account = _fetch_tiger_account(trade_client)

    if tiger_df.empty:
        logger.error("No Tiger positions — falling back to offline")
        return extract_offline(settings)

    all_symbols = list(set(
        tiger_df['symbol'].tolist() + list(settings.TICKER_TIERS.keys())
    ))
    yf_df = _fetch_yfinance_data(all_symbols)
    merged = _merge_and_fix(tiger_df, yf_df, settings)

    total_mv = merged['market_value'].sum()
    logger.info(f"Portfolio total (positions): ${total_mv:,.2f}")
    if account['total_equity'] > 0:
        logger.info(f"Tiger equity (incl cash):    ${account['total_equity']:,.2f}")
        logger.info(f"Implied cash balance:        ${account['total_equity'] - total_mv:,.2f}")

    result = {
        'positions': merged,
        'account': account,
        'quotes': yf_df,
        'timestamp': datetime.now(),
    }
    _save_snapshot(result, settings)
    return result


def _save_snapshot(result, settings):
    """
    Auto-save live data to JSON after every hybrid/yf-only run.
    This keeps --offline mode fresh without manual editing.

    File: output/latest_snapshot.json
    Contains: positions (shares, avg_cost, price, pe) + account summary
    """
    import json
    import os

    df = result['positions']
    snapshot = {
        'timestamp': result['timestamp'].isoformat(),
        'account': result['account'],
        'holdings': [],
    }

    for _, row in df.iterrows():
        snapshot['holdings'].append({
            'symbol': row['symbol'],
            'shares': round(float(row.get('shares', 0)), 6),
            'avg_cost': round(float(row.get('avg_cost', 0)), 4),
            'latest_price': round(float(row.get('latest_price', 0)), 4),
            'pe_ttm': round(float(row['pe_ttm']), 2) if pd.notna(row.get('pe_ttm')) else None,
        })

    os.makedirs('output', exist_ok=True)
    path = 'output/latest_snapshot.json'
    with open(path, 'w') as f:
        json.dump(snapshot, f, indent=2)

    logger.info(f"Snapshot saved → {path} ({len(snapshot['holdings'])} positions)")


def _load_snapshot():
    """
    Load the most recent auto-saved snapshot.
    Returns dict or None if no snapshot exists.
    """
    import json
    import os

    path = 'output/latest_snapshot.json'
    if not os.path.exists(path):
        return None

    with open(path, 'r') as f:
        snapshot = json.load(f)

    logger.info(f"Loaded snapshot from {path} (saved {snapshot['timestamp']})")
    return snapshot


def extract_yf_only(settings):
    """
    TEST MODE: Offline shares + yfinance prices.
    No Tiger credentials needed. Good for testing pipeline changes.
    """
    logger.info("YF-ONLY MODE: offline shares + yfinance prices")

    offline = extract_offline(settings)
    symbols = offline['positions']['symbol'].tolist()
    yf_df = _fetch_yfinance_data(symbols)

    df = offline['positions'].copy()
    price_map = yf_df.set_index('symbol')

    for sym in price_map.index:
        price = price_map.loc[sym, 'latest_price']
        if pd.notna(price) and price > 0:
            mask = df['symbol'] == sym
            df.loc[mask, 'latest_price'] = price
            df.loc[mask, 'market_value'] = df.loc[mask, 'shares'] * price
            df.loc[mask, 'unrealized_pnl'] = df.loc[mask, 'market_value'] - df.loc[mask, 'cost_basis']

        pe = price_map.loc[sym, 'pe_ttm']
        if pd.notna(pe):
            df.loc[df['symbol'] == sym, 'pe_ttm'] = pe

    offline['positions'] = df
    offline['quotes'] = yf_df
    offline['account']['total_equity'] = df['market_value'].sum()
    offline['timestamp'] = datetime.now()
    _save_snapshot(offline, settings)
    return offline


# ════════════════════════════════════════════════════════════
# OFFLINE MODE — Manual snapshot
# ════════════════════════════════════════════════════════════

def extract_offline(settings):
    """
    Offline mode. Tries to load the latest auto-saved snapshot first.
    Falls back to hardcoded data if no snapshot exists.

    The snapshot auto-updates every time you run --hybrid or --yf-only,
    so --offline always uses the most recent live data available.
    """
    snapshot = _load_snapshot()
    if snapshot:
        logger.info(f"Using auto-snapshot from {snapshot['timestamp']}")
        df = pd.DataFrame(snapshot['holdings'])
        df['market_value'] = df['shares'] * df['latest_price']
        df['cost_basis'] = df['shares'] * df['avg_cost']
        df['unrealized_pnl'] = df['market_value'] - df['cost_basis']

        return {
            'positions': df,
            'account': snapshot['account'],
            'quotes': df[['symbol', 'latest_price', 'pe_ttm']].copy(),
            'timestamp': datetime.strptime(snapshot['timestamp'][:19], '%Y-%m-%dT%H:%M:%S'),
        }

    logger.warning("No snapshot found — using hardcoded fallback data")
    return _extract_hardcoded(settings)


def _extract_hardcoded(settings):
    """Hardcoded fallback — only used if no snapshot JSON exists."""
    holdings_data = [
        # Core Equity (post-Tranche 1)
        {'symbol': 'VXUS', 'shares': 54.85,    'avg_cost': 78.50,  'latest_price': 82.50},
        {'symbol': 'VOO',  'shares': 6.97,     'avg_cost': 610.00, 'latest_price': 582.00},
        # Core Bond (post-rotation)
        {'symbol': 'SHY',  'shares': 10.36,    'avg_cost': 82.00,  'latest_price': 82.00},
        {'symbol': 'VTIP', 'shares': 12.39,    'avg_cost': 48.00,  'latest_price': 48.00},
        {'symbol': 'BND',  'shares': 3.47,     'avg_cost': 75.25,  'latest_price': 73.50},
        # Core-Plus
        {'symbol': 'SPYD', 'shares': 16,       'avg_cost': 41.34,  'latest_price': 45.00},
        {'symbol': 'ONEQ', 'shares': 6,        'avg_cost': 56.52,  'latest_price': 82.00},
        # Satellite (post-Tranche 1: RTX added)
        {'symbol': 'GLDM', 'shares': 3.4,      'avg_cost': 103.42, 'latest_price': 89.83},
        {'symbol': 'GOOG', 'shares': 1.3205,   'avg_cost': 310.23, 'latest_price': 274.00},
        {'symbol': 'RTX',  'shares': 3.01,     'avg_cost': 192.00, 'latest_price': 190.00},
        {'symbol': 'NVDA', 'shares': 0.9625,   'avg_cost': 136.35, 'latest_price': 175.68},
        {'symbol': 'TSM',  'shares': 0.5,      'avg_cost': 326.02, 'latest_price': 338.45},
        {'symbol': 'AAPL', 'shares': 0.6849,   'avg_cost': 187.98, 'latest_price': 251.49},
        {'symbol': 'MA',   'shares': 0.3738,   'avg_cost': 544.01, 'latest_price': 480.00},
        {'symbol': 'CAT',  'shares': 0.2423,   'avg_cost': 363.14, 'latest_price': 340.00},
        {'symbol': 'KO',   'shares': 2,        'avg_cost': 70.67,  'latest_price': 78.00},
        # BABA: price approximated — refresh from Tiger app on next pipeline run
        {'symbol': 'BABA', 'shares': 1,        'avg_cost': 164.69, 'latest_price': 85.00},
        {'symbol': 'AON',  'shares': 0.417,    'avg_cost': 374.45, 'latest_price': 310.00},
    ]

    df = pd.DataFrame(holdings_data)
    df['market_value'] = df['shares'] * df['latest_price']
    df['cost_basis'] = df['shares'] * df['avg_cost']
    df['unrealized_pnl'] = df['market_value'] - df['cost_basis']

    pe_ratios = {
        'GOOG': 25.5, 'RTX': 30.0, 'NVDA': 36.0, 'TSM': 24.0,
        'AAPL': 32.0, 'MA': 35.0, 'CAT': 18.0, 'KO': 25.0,
        'BABA': 22.0, 'AON': 28.0,
    }
    df['pe_ttm'] = df['symbol'].map(pe_ratios)

    account = {
        'total_equity': df['market_value'].sum(),
        'cash_balance': 0,
        'buying_power': 0,
        'unrealized_pnl': df['unrealized_pnl'].sum(),
        'timestamp': settings.SNAPSHOT_DATE,
    }

    snapshot_dt = datetime.strptime(settings.SNAPSHOT_DATE, '%Y-%m-%d')
    return {
        'positions': df,
        'account': account,
        'quotes': df[['symbol', 'latest_price', 'pe_ttm']].copy(),
        'timestamp': snapshot_dt,
    }