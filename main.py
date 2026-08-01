"""
main.py — Orchestrator: Extract → Transform → Load

USAGE:
  python main.py                  → Core/Core-Plus book, hybrid mode [DEFAULT]
  python main.py --satellite      → Satellite/risk book instead (config/settings_satellite.py)
  python main.py --yf-only        → Offline shares + yfinance prices (no Tiger needed)
  python main.py --offline        → Manual snapshot data, no API calls
  (flags combine, e.g. python main.py --satellite --offline)

Both books share every module in modules/ — they only differ in which
config/settings*.py module gets loaded, which determines TICKER_TIERS,
OUTPUT_PATH, SNAPSHOT_PATH, DASHBOARD_PATH, WATCHLIST, etc. Each book's
classify_tiers() (modules/transform.py) drops any position not in its own
TICKER_TIERS before totals are computed, so running both against the same
Tiger account never double-counts a position between them.

PIPELINE:
  1. EXTRACT: Pull positions (Tiger) + prices (yfinance)
  2. TRANSFORM: Calculate weights, drift, signals, scores
  3. LOAD: Write everything to Excel with formulas
"""

import sys
import os
import logging
import io
from datetime import datetime

import pandas as pd

import warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='yfinance')
warnings.filterwarnings('ignore', message='.*utcnow.*')

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

for folder in ['output', 'config', 'modules']:
    os.makedirs(folder, exist_ok=True)
    init_file = os.path.join(folder, '__init__.py')
    if not os.path.exists(init_file):
        open(init_file, 'w').close()

_args = sys.argv[1:]
PORTFOLIO = 'satellite' if '--satellite' in _args else 'core'

console_handler = logging.StreamHandler(
    stream=io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
)
file_handler = logging.FileHandler(
    f'output/run_{PORTFOLIO}_{datetime.now():%Y%m%d_%H%M}.log', encoding='utf-8'
)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[console_handler, file_handler]
)
logger = logging.getLogger('PortfolioPipeline')

if PORTFOLIO == 'satellite':
    from config import settings_satellite as settings
else:
    from config import settings
from modules.extract import extract_hybrid, extract_yf_only, extract_offline
from modules.transform import transform_all
from modules.load import load_to_excel
from modules.audit import validate_freshness, price_sanity_check
from modules.screener import run_screener
from modules.dashboard import generate_html_dashboard


def _append_nav_history(summary, settings):
    """
    Append today's NAV to this book's NAV_HISTORY_PATH, so since-inception/
    YTD/monthly return metrics have something to compute against — no such
    history existed before this was added, so those metrics only become
    accurate from whichever day tracking started, not retroactively.

    One entry per calendar day: re-running the pipeline same-day overwrites
    that day's entry rather than appending a duplicate.
    """
    import json

    path = getattr(settings, 'NAV_HISTORY_PATH', 'output/nav_history.json')
    today = datetime.now().strftime('%Y-%m-%d')
    entry = {
        'date': today,
        'total_equity': summary['total_portfolio'],
        'total_pnl': summary['total_pnl'],
        'total_realized_pnl': summary.get('total_realized_pnl', 0),
        'cash_balance': summary.get('cash_balance', 0),
    }

    history = []
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                history = json.load(f)
        except (json.JSONDecodeError, OSError):
            history = []

    history = [h for h in history if h.get('date') != today]
    history.append(entry)
    history.sort(key=lambda h: h['date'])

    with open(path, 'w') as f:
        json.dump(history, f, indent=2)
    logger.info(f"  NAV history: {len(history)} day(s) tracked → {path}")


def run_pipeline(mode='hybrid'):
    logger.info("=" * 60)
    logger.info(f"PORTFOLIO PIPELINE — Book: {PORTFOLIO.upper()} | Mode: {mode.upper()}")
    logger.info("=" * 60)

    # STAGE 0: AUDIT — freshness checks before we trust anything downstream
    is_clean, freshness_report = validate_freshness(settings)

    # STAGE 1: EXTRACT
    logger.info("STAGE 1: Extracting data...")
    if mode == 'hybrid':
        raw_data = extract_hybrid(settings)
    elif mode == 'yf-only':
        raw_data = extract_yf_only(settings)
    else:
        raw_data = extract_offline(settings)

    logger.info(f"  Positions: {len(raw_data['positions'])}")
    logger.info(f"  Account equity: ${raw_data['account']['total_equity']:,.2f}")

    # Price drift check — only meaningful in offline mode (other modes just refreshed prices)
    price_drift = []
    if mode == 'offline':
        price_drift = price_sanity_check(raw_data['positions'], tolerance=0.10)

    # STAGE 2: TRANSFORM
    logger.info("STAGE 2: Calculating metrics...")
    analytics = transform_all(raw_data, settings)
    analytics['audit'] = {
        'freshness': freshness_report,
        'price_drift': price_drift,
        'is_clean': is_clean,
    }

    summary = analytics['summary']
    _append_nav_history(summary, settings)
    logger.info(f"  Total portfolio: ${summary['total_portfolio']:,.2f}")
    for tier, target in settings.TIER_TARGETS.items():
        key_map = {'Core': 'core_pct', 'Core-Plus': 'coreplus_pct', 'Satellite': 'satellite_pct'}
        pct_key = key_map.get(tier)
        if pct_key and pct_key in summary:
            logger.info(f"  {tier}: {summary[pct_key]:.1%} | Target: {target:.0%}")
    logger.info(f"  Total P&L: ${summary['total_pnl']:,.2f} ({summary['total_pnl_pct']:.1%})")

    rebal = analytics['rebalance']
    if not rebal.empty:
        actions = rebal[rebal['signal'] != '✅ HOLD']
        if not actions.empty:
            logger.info(f"  ⚠️ {len(actions)} positions need attention:")
            for _, a in actions.iterrows():
                logger.info(f"    {a['symbol']}: {a['signal']} — {a['action']}")

    entries = analytics['entry_signals']
    if not entries.empty:
        buys = entries[entries['entry_signal'].str.contains('ENTRY', na=False)]
        trims = entries[entries['entry_signal'].str.contains('TRIM', na=False)]
        if not buys.empty:
            logger.info(f"  💡 Entry opportunities: {', '.join(buys['symbol'].tolist())}")
        if not trims.empty:
            logger.info(f"  🚨 Trim candidates: {', '.join(trims['symbol'].tolist())}")

    # STAGE 2b: SCREENER — watchlist valuation (skipped in offline mode)
    if mode != 'offline':
        logger.info("STAGE 2b: Running watchlist screener...")
        analytics['screener'] = run_screener(settings)
        logger.info(f"  Screener: {len(analytics['screener'])} tickers")
    else:
        analytics['screener'] = pd.DataFrame()

    # STAGE 3: LOAD
    logger.info("STAGE 3: Writing to Excel...")
    output_path = load_to_excel(analytics, settings)
    logger.info(f"  Output: {output_path}")

    # STAGE 3b: Generate HTML Dashboard
    logger.info("STAGE 3b: Generating HTML dashboard...")
    try:
        dashboard_path = generate_html_dashboard(
            settings,
            snapshot_path=getattr(settings, 'SNAPSHOT_PATH', 'output/latest_snapshot.json'),
            output_path=getattr(settings, 'DASHBOARD_PATH', 'output/dashboard.html')
        )
        logger.info(f"  Dashboard: {dashboard_path}")
    except Exception as e:
        logger.warning(f"  Dashboard generation failed: {e}")

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    return analytics


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--offline' in args:
        mode = 'offline'
    elif '--yf-only' in args:
        mode = 'yf-only'
    else:
        mode = 'hybrid'
    run_pipeline(mode=mode)