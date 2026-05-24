"""
audit.py — Pre-flight checks for data staleness and price drift.

Two responsibilities:
  1. validate_freshness()    — date arithmetic on settings.DATA_FRESHNESS
  2. price_sanity_check()    — compares snapshot prices to live yfinance spot

Both are surfaced to the weekly review via the Audit sheet in portfolio_tracker.xlsx.
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


def price_sanity_check(holdings_df, tolerance=0.10):
    """
    Compare each held position's `latest_price` to live yfinance spot.

    Flags any position whose drift exceeds `tolerance` (default 10%).
    Useful for catching cases where SNAPSHOT_DATE was bumped but the
    hardcoded prices in extract_offline() were not refreshed.

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

    for _, row in holdings_df.iterrows():
        sym = row.get('symbol')
        snap_price = row.get('latest_price')
        if not sym or snap_price is None or snap_price <= 0:
            continue
        try:
            fast = yf.Ticker(sym).fast_info
            spot = fast.get('last_price') or fast.get('lastPrice')
            if spot is None or spot <= 0:
                continue
            spot = float(spot)
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
