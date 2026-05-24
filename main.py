"""
main.py — Orchestrator: Extract → Transform → Load

USAGE:
  python main.py              → Hybrid mode (Tiger + yfinance) [DEFAULT]
  python main.py --hybrid     → Same as above, explicit
  python main.py --yf-only    → Offline shares + yfinance prices (no Tiger needed)
  python main.py --offline    → Manual snapshot data, no API calls

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

console_handler = logging.StreamHandler(
    stream=io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
)
file_handler = logging.FileHandler(
    f'output/run_{datetime.now():%Y%m%d_%H%M}.log', encoding='utf-8'
)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[console_handler, file_handler]
)
logger = logging.getLogger('PortfolioPipeline')

from config import settings
from modules.extract import extract_hybrid, extract_yf_only, extract_offline
from modules.transform import transform_all
from modules.load import load_to_excel
from modules.audit import validate_freshness, price_sanity_check


def run_pipeline(mode='hybrid'):
    logger.info("=" * 60)
    logger.info(f"PORTFOLIO PIPELINE — Mode: {mode.upper()}")
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
    logger.info(f"  Total portfolio: ${summary['total_portfolio']:,.2f}")
    logger.info(f"  Core: {summary['core_pct']:.1%} | Target: 68%")
    logger.info(f"  Satellite: {summary['satellite_pct']:.1%} | Target: 21%")
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

    # STAGE 3: LOAD
    logger.info("STAGE 3: Writing to Excel...")
    output_path = load_to_excel(analytics, settings)
    logger.info(f"  Output: {output_path}")

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