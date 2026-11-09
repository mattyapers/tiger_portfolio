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

from modules.extract import (
    _fetch_yfinance_data, _merge_and_fix, _save_snapshot, extract_offline,
    _connect_tiger, _fetch_tiger_positions, _fetch_tiger_account,
)

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
# MULTI-BROKER MERGE — Tiger + IBKR are separate pools, same tickers
# can exist in both; totals must SUM, not pick one broker over the
# other, or holdings for any ticker split across accounts under-report.
# ════════════════════════════════════════════════════════════

def _merge_broker_positions(broker_dfs):
    """
    Combine multiple brokers' "what you OWN" DataFrames into one.
    Each input DataFrame must share the extract.py/extract_ibkr.py contract:
    symbol, tiger_shares, avg_cost, tiger_market_value, unrealized_pnl,
    realized_pnl (the 'tiger_*' naming is kept from Tiger's original
    column names so _merge_and_fix() needs no changes regardless of
    which broker(s) fed it).

    Per symbol: shares SUM across brokers; avg_cost becomes a
    shares-weighted average (so a ticker split 60/40 between two
    brokers at different cost bases gets one blended cost basis, not
    whichever broker happened to load last); P&L fields sum, treating
    missing values (IBKR's positions() doesn't return P&L) as 0.
    """
    frames = [df for df in broker_dfs if df is not None and not df.empty]
    if not frames:
        return pd.DataFrame()
    if len(frames) == 1:
        return frames[0]

    combined = pd.concat(frames, ignore_index=True)
    combined['_cost_contribution'] = combined['tiger_shares'] * combined['avg_cost']

    grouped = combined.groupby('symbol', as_index=False).agg(
        tiger_shares=('tiger_shares', 'sum'),
        tiger_market_value=('tiger_market_value', 'sum'),
        _cost_contribution=('_cost_contribution', 'sum'),
        unrealized_pnl=('unrealized_pnl', lambda s: s.fillna(0).sum()),
        realized_pnl=('realized_pnl', lambda s: s.fillna(0).sum()),
    )
    grouped['avg_cost'] = grouped['_cost_contribution'] / grouped['tiger_shares']
    grouped = grouped.drop(columns=['_cost_contribution'])

    n_multi = (combined.groupby('symbol').size() > 1).sum()
    if n_multi:
        logger.info(f"Multi-broker merge: {n_multi} ticker(s) held across more than one broker, combined")
    return grouped


# ════════════════════════════════════════════════════════════
# MANUAL ENTRY — IBKR Lite (commission-free) accounts have NO TWS/API
# access at all; only IBKR Pro unlocks it. This path skips ib_async/TWS
# entirely and reads hand-entered positions from settings instead, so the
# multi-broker merge still works without a live socket connection.
# ════════════════════════════════════════════════════════════

_fx_cache = {}


def _get_fx_to_usd(currency):
    """Live FX rate to convert 1 unit of `currency` into USD. Cached per run."""
    if currency == 'USD':
        return 1.0
    if currency in _fx_cache:
        return _fx_cache[currency]

    import yfinance as yf
    rate = 1.0
    try:
        info = yf.Ticker(f'{currency}USD=X').info or {}
        fetched = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
        if fetched:
            rate = float(fetched)
    except Exception as e:
        logger.warning(f"FX fetch failed for {currency}->USD: {e} — defaulting to 1.0 (will misstate value)")

    _fx_cache[currency] = rate
    return rate


def _fetch_ibkr_positions_manual(settings):
    """
    Build the "what you OWN" DataFrame from IBKR_MANUAL_POSITIONS instead
    of a live API call. avg_cost is stored in the position's LISTING
    currency (see IBKR_YF_SYMBOL_MAP) and converted to USD here so
    downstream math (_merge_and_fix, tier weights) stays single-currency.
    """
    manual = getattr(settings, 'IBKR_MANUAL_POSITIONS', {})
    if not manual:
        logger.warning("No IBKR_MANUAL_POSITIONS configured")
        return pd.DataFrame()

    yf_map = getattr(settings, 'IBKR_YF_SYMBOL_MAP', {})
    rows = []
    for symbol, pos in manual.items():
        currency = yf_map.get(symbol, {}).get('currency', 'USD')
        fx = _get_fx_to_usd(currency)
        avg_cost_usd = pos['avg_cost'] * fx
        shares = pos['shares']
        rows.append({
            'symbol': symbol,
            'tiger_shares': shares,
            'avg_cost': avg_cost_usd,
            'tiger_market_value': shares * avg_cost_usd,
            'unrealized_pnl': None,
            'realized_pnl': None,
        })

    df = pd.DataFrame(rows)
    logger.info(f"IBKR manual: {len(df)} position(s) — hand-entered (API locked, IBKR Lite)")
    return df


def _fetch_yfinance_data_ibkr(symbols, settings):
    """
    yfinance fetch for IBKR manual positions: resolves each display symbol
    to its LSE yfinance ticker (IBKR_YF_SYMBOL_MAP) and converts any
    non-USD price back to USD, same FX cache as the position-side convert,
    so price and avg_cost end up in the same currency for every row.
    """
    yf_map = getattr(settings, 'IBKR_YF_SYMBOL_MAP', {})
    yf_symbols = [yf_map.get(s, {}).get('yf', s) for s in symbols]
    df = _fetch_yfinance_data(yf_symbols)

    reverse = {v['yf']: k for k, v in yf_map.items()}
    df['symbol'] = df['symbol'].map(lambda s: reverse.get(s, s))

    for idx, row in df.iterrows():
        currency = yf_map.get(row['symbol'], {}).get('currency', 'USD')
        if currency != 'USD' and pd.notna(row['latest_price']):
            df.at[idx, 'latest_price'] = row['latest_price'] * _get_fx_to_usd(currency)

    return df


def extract_multi_broker_manual(settings):
    """
    Tiger (live API) + IBKR (hand-entered, since IBKR Lite blocks API
    access) positions, summed per ticker, + yfinance prices. Use this when
    --ibkr/--multi-broker can't connect because the IBKR account is Lite
    tier — update IBKR_MANUAL_POSITIONS from the app each cycle instead.
    """
    logger.info("=" * 50)
    logger.info("HYBRID MODE (MULTI-BROKER, IBKR MANUAL): Tiger + IBKR(manual) + yfinance")
    logger.info("=" * 50)

    trade_client, _ = _connect_tiger(settings)
    tiger_df = _fetch_tiger_positions(trade_client)
    tiger_account = _fetch_tiger_account(trade_client)

    ibkr_df = _fetch_ibkr_positions_manual(settings)

    merged_positions = _merge_broker_positions([tiger_df, ibkr_df])
    if merged_positions.empty:
        logger.error("No positions from either source — falling back to offline")
        return extract_offline(settings)

    all_symbols = list(set(
        merged_positions['symbol'].tolist() + list(settings.TICKER_TIERS.keys())
    ))
    yf_df = _fetch_yfinance_data_ibkr(all_symbols, settings)
    merged = _merge_and_fix(merged_positions, yf_df, settings)

    # IBKR cash isn't tracked here (manual entry covers positions only) —
    # account total reflects Tiger's cash + both brokers' position value.
    total_mv = merged['market_value'].sum()
    ibkr_mv = merged.loc[merged['symbol'].isin(ibkr_df['symbol']), 'market_value'].sum() if not ibkr_df.empty else 0
    account = {
        'total_equity': tiger_account.get('total_equity', 0) + ibkr_mv,
        'cash_balance': tiger_account.get('cash_balance', 0),
        'buying_power': tiger_account.get('buying_power', 0),
        'unrealized_pnl': tiger_account.get('unrealized_pnl', 0),
        'timestamp': datetime.now().isoformat(),
    }

    logger.info(f"Portfolio total (positions, both brokers): ${total_mv:,.2f}")
    if account['total_equity'] > 0:
        logger.info(f"Combined equity (Tiger equity + IBKR positions, no IBKR cash): ${account['total_equity']:,.2f}")

    result = {
        'positions': merged,
        'account': account,
        'quotes': yf_df,
        'timestamp': datetime.now(),
    }
    _save_snapshot(result, settings)
    return result


def extract_multi_broker_hybrid(settings):
    """
    Tiger + IBKR positions, summed per ticker, + yfinance prices.
    Use this (not extract_ibkr_hybrid) when the two accounts hold
    genuinely separate/overlapping positions that both need to count
    toward the same book's totals — extract_ibkr_hybrid alone treats
    IBKR as a drop-in REPLACEMENT for Tiger, which under-reports any
    ticker actually split across both accounts.
    """
    logger.info("=" * 50)
    logger.info("HYBRID MODE (MULTI-BROKER): Tiger + IBKR + yfinance")
    logger.info("=" * 50)

    trade_client, _ = _connect_tiger(settings)
    tiger_df = _fetch_tiger_positions(trade_client)
    tiger_account = _fetch_tiger_account(trade_client)

    ib = _connect_ibkr(settings)
    try:
        ibkr_df = _fetch_ibkr_positions(ib, settings)
        ibkr_account = _fetch_ibkr_account(ib, settings)
    finally:
        ib.disconnect()

    merged_positions = _merge_broker_positions([tiger_df, ibkr_df])
    if merged_positions.empty:
        logger.error("No positions from either broker — falling back to offline")
        return extract_offline(settings)

    account = {
        'total_equity': tiger_account.get('total_equity', 0) + ibkr_account.get('total_equity', 0),
        'cash_balance': tiger_account.get('cash_balance', 0) + ibkr_account.get('cash_balance', 0),
        'buying_power': tiger_account.get('buying_power', 0) + ibkr_account.get('buying_power', 0),
        'unrealized_pnl': tiger_account.get('unrealized_pnl', 0) + ibkr_account.get('unrealized_pnl', 0),
        'timestamp': datetime.now().isoformat(),
    }

    all_symbols = list(set(
        merged_positions['symbol'].tolist() + list(settings.TICKER_TIERS.keys())
    ))
    yf_df = _fetch_yfinance_data(all_symbols)
    merged = _merge_and_fix(merged_positions, yf_df, settings)

    total_mv = merged['market_value'].sum()
    logger.info(f"Portfolio total (positions, both brokers): ${total_mv:,.2f}")
    if account['total_equity'] > 0:
        logger.info(f"Combined equity (incl cash, both brokers): ${account['total_equity']:,.2f}")

    result = {
        'positions': merged,
        'account': account,
        'quotes': yf_df,
        'timestamp': datetime.now(),
    }
    _save_snapshot(result, settings)
    return result


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
