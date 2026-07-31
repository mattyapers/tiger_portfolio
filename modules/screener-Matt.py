"""
screener.py — Watchlist valuation screener.

Fetches live yfinance data for all tickers in WATCHLIST and scores them
against P/E history, FCF yield, and current regime fit. Results go to
the Screener sheet in portfolio_tracker.xlsx.

Skipped automatically in --offline mode (no internet).
"""

import yfinance as yf
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def run_screener(settings):
    """
    Fetch and score all WATCHLIST tickers.
    Returns a DataFrame ready for write_screener_sheet().
    """
    tickers = _extract_tickers(settings.WATCHLIST)
    if not tickers:
        return pd.DataFrame()

    logger.info(f"Screener: fetching {len(tickers)} watchlist tickers...")
    rows = []
    for ticker in tickers:
        rows.append(_fetch_ticker(ticker, settings))

    df = pd.DataFrame(rows)
    logger.info(f"  Screener complete: {len(df)} rows")
    return df


def _extract_tickers(watchlist):
    seen = []
    for entry in watchlist.values():
        t = entry.get('ticker')
        if t and t not in seen:
            seen.append(t)
    return seen


def _fetch_ticker(ticker, settings):
    pe_5y = settings.PE_5Y_AVERAGES.get(ticker)
    fit = settings.WATCHLIST_REGIME_FIT.get(ticker, {})
    base = {
        'symbol': ticker,
        'pe_5y_avg': pe_5y,
        'regime_fit': fit.get('score', '—'),
        'regime_note': fit.get('reason', ''),
    }
    try:
        info = yf.Ticker(ticker).info
        price = info.get('currentPrice') or info.get('regularMarketPrice')
        pe_ttm = info.get('trailingPE')
        fwd_pe = info.get('forwardPE')
        fcf = info.get('freeCashflow')
        mcap = info.get('marketCap')

        pe_premium = (pe_ttm / pe_5y - 1) if (pe_ttm and pe_5y) else None
        fcf_yield = (fcf / mcap * 100) if (fcf and mcap) else None

        return {
            **base,
            'price': price,
            'pe_ttm': round(pe_ttm, 1) if pe_ttm else None,
            'fwd_pe': round(fwd_pe, 1) if fwd_pe else None,
            'pe_premium_pct': round(pe_premium * 100, 1) if pe_premium is not None else None,
            'fcf_yield_pct': round(fcf_yield, 1) if fcf_yield is not None else None,
            'signal': _valuation_signal(pe_ttm, pe_5y, pe_premium, settings),
        }
    except Exception as e:
        logger.warning(f"  {ticker}: fetch failed — {e}")
        return {**base, 'price': None, 'pe_ttm': None, 'fwd_pe': None,
                'pe_premium_pct': None, 'fcf_yield_pct': None, 'signal': 'ERR'}


def _valuation_signal(pe_ttm, pe_5y, pe_premium, settings):
    rules = settings.SIGNAL_RULES
    if pe_ttm is None:
        return '— No P/E data'
    if pe_premium is not None:
        if pe_ttm > rules['pe_max'] and pe_premium > rules['pe_premium_trim']:
            return '🚨 EXPENSIVE'
        if pe_ttm > rules['pe_max'] or pe_premium > rules['pe_premium_trim']:
            return '⚠️ WATCH'
        if pe_premium < -0.15:
            return '💡 VALUE'
    elif pe_ttm > rules['pe_max']:
        return '⚠️ PE HIGH'
    return '✅ FAIR'
