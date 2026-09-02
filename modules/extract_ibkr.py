"""
extract_ibkr.py — Stage 1 (IBKR variant): Pull portfolio + market data via
Interactive Brokers instead of Tiger.

STATUS: draft, untested against a live IBKR account — wire up alongside
extract.py's Tiger path once you've actually got TWS/IB Gateway running.
Mirrors extract.py's hybrid architecture exactly, just swaps the "what you
OWN" source:

  IBKR API (via ib_async) → what you OWN: shares, avg_cost, market_value, P&L
  yfinance (free)         → what it's WORTH: latest_price, pe_ttm, dividends
  Merge + validate        → same _merge_and_fix()/_save_snapshot() as extract.py

REQUIRES:
  pip install ib_async   # maintained fork of the now-unmaintained ib_insync,
                          # same API surface (import ib_async as ib_insync-compatible)
  TWS or IB Gateway running locally, API access enabled (Configure > API >
  Settings > Enable ActiveX and Socket Clients), paper or live port open.

CONFIG (add to config/settings.py / config/settings_satellite.py — optional,
only needed once you actually run --ibkr):
  IBKR_HOST = '127.0.0.1'
  IBKR_PORT = 7497          # 7497 = TWS paper, 7496 = TWS live,
                             # 4002 = IB Gateway paper, 4001 = IB Gateway live
  IBKR_CLIENT_ID = 1        # any int not in use by another API client
  IBKR_ACCOUNT = 'DU1234567'  # your account id, paper or live

Unlike Tiger (RSA-signed REST calls), IBKR's API is a persistent socket
connection to a locally-running TWS/Gateway process — there's no way to
run this from a machine that doesn't have TWS/Gateway open, which is why
this stays a separate opt-in module rather than a drop-in Tiger replacement.
"""

import pandas as pd
import logging
from datetime import datetime

from modules.extract import _fetch_yfinance_data, _merge_and_fix, _save_snapshot, extract_offline

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
# IBKR API — What you OWN (via ib_async)
# ════════════════════════════════════════════════════════════

def _connect_ibkr(settings):
    from ib_async import IB

    ib = IB()
    ib.connect(
        host=getattr(settings, 'IBKR_HOST', '127.0.0.1'),
        port=getattr(settings, 'IBKR_PORT', 7497),
        clientId=getattr(settings, 'IBKR_CLIENT_ID', 1),
        readonly=True,   # this pipeline only ever reads — never place orders through it
    )
    logger.info(f"Connected to IBKR API | Account: {getattr(settings, 'IBKR_ACCOUNT', '(default)')}")
    return ib


def _fetch_ibkr_positions(ib, settings):
    """
    Pull positions from IBKR. Uses ib.positions() (raw shares/avg_cost),
    not ib.portfolio() — keeps the same "what you OWN" contract as Tiger's
    _fetch_tiger_positions() so _merge_and_fix() doesn't need to branch.
    """
    account = getattr(settings, 'IBKR_ACCOUNT', None)
    positions = ib.positions(account=account) if account else ib.positions()

    if not positions:
        logger.warning("No positions from IBKR API")
        return pd.DataFrame()

    rows = []
    for pos in positions:
        rows.append({
            'symbol': pos.contract.symbol,
            'tiger_shares': pos.position,          # kept as 'tiger_*' so _merge_and_fix() is unmodified
            'avg_cost': pos.avgCost,
            'tiger_market_value': pos.position * pos.avgCost,  # IBKR doesn't return mkt value on positions(); refined post-merge via yfinance price
            'unrealized_pnl': None,   # not on positions(); would need ib.portfolio() or reqPnLSingle for live P&L
            'realized_pnl': None,
        })

    df = pd.DataFrame(rows)
    logger.info(f"IBKR API: {len(df)} positions")
    return df


def _fetch_ibkr_account(ib, settings):
    """Pull account summary from IBKR via accountSummary()."""
    account = getattr(settings, 'IBKR_ACCOUNT', None)
    try:
        tags = ib.accountSummary(account=account) if account else ib.accountSummary()
        values = {t.tag: t.value for t in tags if t.currency in ('USD', 'BASE')}
        return {
            'total_equity': float(values.get('NetLiquidation', 0) or 0),
            'cash_balance': float(values.get('TotalCashValue', 0) or 0),
            'buying_power': float(values.get('BuyingPower', 0) or 0),
            'unrealized_pnl': float(values.get('UnrealizedPnL', 0) or 0),
            'timestamp': datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"IBKR account summary failed: {e}")
        return {'total_equity': 0, 'cash_balance': 0, 'buying_power': 0,
                'unrealized_pnl': 0, 'timestamp': datetime.now().isoformat()}


# ════════════════════════════════════════════════════════════
# EXTRACT MODE — mirrors extract.py's extract_hybrid()
# ════════════════════════════════════════════════════════════

def extract_ibkr_hybrid(settings):
    """
    IBKR positions + yfinance prices. Same shape as extract_hybrid() in
    extract.py — reuses its yfinance fetch, merge/fractional-share-fix,
    and snapshot save so downstream transform.py/load.py need zero changes.
    """
    logger.info("=" * 50)
    logger.info("HYBRID MODE (IBKR): IBKR API + yfinance")
    logger.info("=" * 50)

    ib = _connect_ibkr(settings)
    try:
        ibkr_df = _fetch_ibkr_positions(ib, settings)
        account = _fetch_ibkr_account(ib, settings)
    finally:
        ib.disconnect()

    if ibkr_df.empty:
        logger.error("No IBKR positions — falling back to offline")
        return extract_offline(settings)

    all_symbols = list(set(
        ibkr_df['symbol'].tolist() + list(settings.TICKER_TIERS.keys())
    ))
    yf_df = _fetch_yfinance_data(all_symbols)
    merged = _merge_and_fix(ibkr_df, yf_df, settings)

    total_mv = merged['market_value'].sum()
    logger.info(f"Portfolio total (positions): ${total_mv:,.2f}")
    if account['total_equity'] > 0:
        logger.info(f"IBKR equity (incl cash):     ${account['total_equity']:,.2f}")

    result = {
        'positions': merged,
        'account': account,
        'quotes': yf_df,
        'timestamp': datetime.now(),
    }
    _save_snapshot(result, settings)
    return result
