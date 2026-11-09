"""
audit.py — Pre-flight checks for data staleness and price drift.

Three responsibilities:
  1. validate_freshness()      — date arithmetic on settings.DATA_FRESHNESS
  2. price_sanity_check()      — compares snapshot prices to live yfinance spot
  3. check_unmapped_tickers()  — flags Tiger positions mapped into NEITHER
                                 book's TICKER_TIERS (the D05.SI/MRVL bug,
                                 2026-11-09: a new Tiger buy silently vanishes
                                 from both books' totals until someone
                                 notices by hand)

All three are surfaced to the weekly review via the Audit sheet in
portfolio_tracker.xlsx / satellite_tracker.xlsx.
"""

from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def validate_freshness(settings):
    """
    Compare each DATA_FRESHNESS entry's last-updated date to today.

    Returns:
        (is_clean: bool, report: list[dict])
        is_clean is False if ANY item exceeds its cadence_days budget.
    """
    today = datetime.now()
    report = []
    is_clean = True

    freshness = getattr(settings, 'DATA_FRESHNESS', {})
    if not freshness:
        logger.warning("settings.DATA_FRESHNESS not defined — skipping freshness audit")
        return True, []

    for key, meta in freshness.items():
        last = datetime.strptime(meta['value'], '%Y-%m-%d')
        age_days = (today - last).days
        cadence = meta['cadence_days']
        is_stale = age_days > cadence
        if is_stale:
            is_clean = False
        report.append({
            'key': key,
            'item': meta['label'],
            'last_updated': meta['value'],
            'age_days': age_days,
            'cadence_days': cadence,
            'status': '🚨 STALE' if is_stale else '✅ FRESH',
        })

    logger.info("=" * 60)
    logger.info("DATA FRESHNESS AUDIT")
    logger.info("=" * 60)
    for r in report:
        logger.info(
            f"  {r['status']} | {r['item']:42} | "
            f"{r['age_days']:>3}d old (cadence: {r['cadence_days']}d)"
        )
    if not is_clean:
        logger.warning("⚠️  One or more data sources are stale — see report.")

    return is_clean, report


def price_sanity_check(holdings_df, tolerance=0.10, yf_symbol_map=None):
    """
    Compare each held position's `latest_price` to live yfinance spot.

    Flags any position whose drift exceeds `tolerance` (default 10%).
    Useful for catching cases where SNAPSHOT_DATE was bumped but the
    hardcoded prices in extract_offline() were not refreshed.

    yf_symbol_map: optional {display_symbol: {'yf': yf_ticker, 'currency': ..}}
    override for symbols yfinance can't resolve directly (e.g. LSE UCITS
    funds need a .L suffix) — see settings.IBKR_YF_SYMBOL_MAP. snap_price
    is assumed to already be in USD (extract_ibkr.py converts at fetch
    time), so a non-USD spot is converted to USD here before comparing.

    Returns: list[dict] of flagged positions. Empty list if all within tolerance.
    Returns empty list (not None) on yfinance failures so the audit always renders.
    """
    flagged = []
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance not available — skipping price sanity check")
        return flagged

    if holdings_df is None or holdings_df.empty:
        return flagged

    yf_symbol_map = yf_symbol_map or {}

    for _, row in holdings_df.iterrows():
        sym = row.get('symbol')
        snap_price = row.get('latest_price')
        if not sym or snap_price is None or snap_price <= 0:
            continue
        mapping = yf_symbol_map.get(sym, {})
        yf_symbol = mapping.get('yf', sym)
        try:
            fast = yf.Ticker(yf_symbol).fast_info
            spot = fast.get('last_price') or fast.get('lastPrice')
            if spot is None or spot <= 0:
                continue
            spot = float(spot)
            currency = mapping.get('currency', 'USD')
            if currency != 'USD':
                from modules.extract_ibkr import _get_fx_to_usd
                spot *= _get_fx_to_usd(currency)
            drift = (spot - snap_price) / snap_price
            if abs(drift) > tolerance:
                flagged.append({
                    'symbol': sym,
                    'snapshot_price': round(float(snap_price), 4),
                    'spot_price': round(spot, 4),
                    'drift_pct': round(drift, 4),
                })
        except Exception as e:
            logger.warning(f"Price check failed for {sym}: {type(e).__name__}")
            continue

    if flagged:
        logger.warning(f"⚠️  {len(flagged)} position(s) drifted >{tolerance:.0%} from snapshot:")
        for f in flagged:
            logger.warning(
                f"    {f['symbol']}: snapshot ${f['snapshot_price']:.2f} "
                f"vs spot ${f['spot_price']:.2f} ({f['drift_pct']:+.1%})"
            )
    else:
        logger.info(f"✅ Price sanity check: all positions within {tolerance:.0%} of spot")

    return flagged


def check_unmapped_tickers(positions_df):
    """
    Flag any live Tiger position not mapped into EITHER book's TICKER_TIERS.

    classify_tiers() (modules/transform.py) silently drops a position not in
    THIS book's TICKER_TIERS as "Unknown" — by design, so Core/Core-Plus and
    Satellite don't double-count each other's holdings. But a ticker missing
    from BOTH books means it's a real Tiger position nobody is tracking at
    all: it never shows in Excel, the dashboard, or either book's totals,
    and nothing used to flag that (see D05.SI/MRVL, discovered 2026-11-09
    only because the user noticed the dollar total looked low).

    Imports both settings modules directly rather than taking them as a
    param, so this can run from either book's main.py without threading
    the other book's settings through run_pipeline().

    Returns: list[str] of unmapped symbols, sorted. Empty list if none.
    """
    if positions_df is None or positions_df.empty or 'symbol' not in positions_df.columns:
        return []

    from config import settings as core_settings
    from config import settings_satellite as satellite_settings

    known = set(core_settings.TICKER_TIERS) | set(satellite_settings.TICKER_TIERS)
    held = set(positions_df['symbol'].dropna())
    unmapped = sorted(held - known)

    if unmapped:
        logger.warning(f"🚨 {len(unmapped)} ticker(s) held on Tiger but mapped in NEITHER book: {unmapped}")
        logger.warning("   Silently excluded from both books' totals/dashboards. Add to the "
                        "appropriate book's TICKER_TIERS (settings_satellite.py for a new "
                        "discretionary buy; settings.py for a new Core/Core-Plus index fund).")
    else:
        logger.info("✅ All held tickers mapped to a book")

    return unmapped
