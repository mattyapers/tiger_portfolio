"""
settings.py — Single source of truth for Core/Core-Plus portfolio rules and API config.

Credentials (TIGER_ID, ACCOUNT, PRIVATE_KEY_PATH, LICENSE) are loaded from .env
via python-dotenv. The .env file is gitignored. See .env.example for the schema.

SPLIT 2026-07-24: This module now covers Core + Core-Plus only — the
long-term, passive buy-and-hold sleeve. The former Satellite/active sleeve
now lives in the sibling module `config/settings_satellite.py`, so the two
risk books don't get blended into one pie and don't double-count each
other's positions. Both books point at the same Tiger account and share
every module in modules/; `main.py --satellite` picks settings_satellite.py
instead of this file. Each book's classify_tiers() (modules/transform.py)
drops any position not in its own TICKER_TIERS before computing totals —
that's the mechanism that keeps the two books from bleeding into each
other's weight/drift math.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# TIGER BROKERS API CONFIG (loaded from .env)
# ============================================================
TIGER_ID = os.getenv('TIGER_ID', '')
ACCOUNT = os.getenv('TIGER_ACCOUNT', '')
PRIVATE_KEY_PATH = os.getenv('TIGER_PRIVATE_KEY_PATH', 'config/tiger_private_key.pem')
LICENSE = os.getenv('TIGER_LICENSE', 'TBSG')

# ============================================================
# IBKR API CONFIG (loaded from .env — only used with --ibkr / --multi-broker)
# ============================================================
IBKR_HOST = os.getenv('IBKR_HOST', '127.0.0.1')
IBKR_PORT = int(os.getenv('IBKR_PORT', '7496'))
IBKR_CLIENT_ID = int(os.getenv('IBKR_CLIENT_ID', '1'))
IBKR_ACCOUNT = os.getenv('IBKR_ACCOUNT', '')

# ============================================================
# PORTFOLIO STRUCTURE — Core + Core-Plus only (long-term sleeve)
# ============================================================
# Rescaled from the original 68/11/21 split, dropping Satellite (21%) and
# redistributing its share proportionally across Core and Core-Plus so the
# two remaining tiers still sum to 1.00: 68/(68+11)=0.8608, 11/79=0.1392.
TIER_TARGETS = {
    'Core': 0.86,
    'Core-Plus': 0.14,
}

# Which tickers belong to which tier
# Core-Bond is a sub-tier of Core for duration tracking
TICKER_TIERS = {
    'VXUS': 'Core',
    'VOO':  'Core',
    'BND':  'Core-Bond',
    'IEF':  'Core-Bond',
    'SPTL': 'Core-Bond',
    'SHY':  'Core-Bond',
    'VTIP': 'Core-Bond',
    'SPYD': 'Core-Plus',
    'ONEQ': 'Core-Plus',
    # IBKR account (manual entry — see IBKR_MANUAL_POSITIONS below).
    # UCITS equity funds -> Core (mirror VXUS/VOO); UCITS bond funds ->
    # Core-Bond; the IBKR stock itself -> Core-Plus (single-name, not an
    # index fund, fits alongside SPYD/ONEQ).
    'CSPX': 'Core',
    'EIMI': 'Core',
    'XUSE': 'Core',
    'TIP5': 'Core-Bond',
    'IBTS': 'Core-Bond',
    'IBKR': 'Core-Plus',
}

# ============================================================
# IBKR MANUAL POSITIONS — API locked (IBKR Lite = commission-free, no TWS
# API access; only IBKR Pro unlocks it). extract_multi_broker_manual()
# (modules/extract_ibkr.py) reads this instead of connecting live.
# Update by hand each cycle from the IBKR app/web positions screen —
# shares + avg cost in the LISTING currency (see IBKR_YF_SYMBOL_MAP for
# which ones are GBP vs USD; conversion to USD happens automatically at
# fetch time using a live FX rate).
# ============================================================
IBKR_MANUAL_POSITIONS = {
    # Captured 2026-11-09 from IBKR positions screen.
    'IBKR': {'shares': 0.5478,   'avg_cost': 85.765},   # USD
    'TIP5': {'shares': 86.5785,  'avg_cost': 5.020},     # USD
    'EIMI': {'shares': 10.4315,  'avg_cost': 55.063},    # USD
    # CSPX avg cost truncated in the source screenshot ("831....") —
    # placeholder below, confirm exact figure from IBKR and correct.
    'CSPX': {'shares': 2.2593,   'avg_cost': 831.00},    # USD (UNCONFIRMED — verify)
    'XUSE': {'shares': 217.6149, 'avg_cost': 5.3848},    # GBP
    'IBTS': {'shares': 0.9,      'avg_cost': 95.562},    # GBP
}

# Display symbol -> (yfinance ticker, listing currency). LSE UCITS funds
# need the .L suffix for yfinance; IBKR stock itself trades directly on
# NASDAQ under its own ticker, no suffix.
IBKR_YF_SYMBOL_MAP = {
    'CSPX': {'yf': 'CSPX.L', 'currency': 'USD'},
    'EIMI': {'yf': 'EIMI.L', 'currency': 'USD'},
    'XUSE': {'yf': 'XUSE.L', 'currency': 'GBP'},
    'TIP5': {'yf': 'TIP5.L', 'currency': 'USD'},
    'IBTS': {'yf': 'IBTS.L', 'currency': 'GBP'},
    'IBKR': {'yf': 'IBKR',   'currency': 'USD'},
}

# ============================================================
# SATELLITE-ONLY CONFIG — kept as empty dicts, not removed
# ============================================================
# load.py's load_to_excel() and transform.py's score_entry_exit() /
# generate_rebalance_signals() access these attributes unconditionally
# (they don't check "does a Satellite tier exist" first) — deleting them
# outright raises AttributeError even though there are zero Satellite
# positions in this book. Real values live in config/settings_satellite.py now.
SATELLITE_TARGETS = {}
PE_5Y_AVERAGES = {}

# ============================================================
# REBALANCING RULES
# ============================================================
# NOTE: generate_rebalance_signals() in transform.py only produces
# per-position signals for tier == 'Satellite', which no longer exists in
# this tracker — these thresholds are dormant here. Tier-level drift
# (Core/Core-Plus vs target) is still computed via calculate_tier_drift()
# using the hardcoded 3%/5% bands in transform.py, independent of this dict.
REBALANCE_RULES = {
    'drift_threshold': 0.03,
    'max_position_pct': 0.15,
    'review_cycle_days': 14,
    'correlation_target': 0.50,
    'correlation_max': 0.75,
}

# ============================================================
# ENTRY / EXIT SIGNALS
# ============================================================
# NOTE: score_entry_exit() in transform.py only scores tier == 'Satellite'
# positions — dormant here for the same reason as REBALANCE_RULES above.
SIGNAL_RULES = {
    'pe_max': 30,
    'pe_premium_trim': 0.25,
    'stop_loss_pct': -0.15,
    'take_profit_pct': 1.00,
}

# ============================================================
# MACRO REGIME — Updated 2026-07-24
# ============================================================
# Still relevant here: drives Core-Bond duration target via REGIME_PLAYBOOK.
# Satellite-specific fields (satellite_overrides) live in
# config/settings_satellite.py now, not here.
MACRO_REGIME = {
    'as_of_date': '2026-11-09',
    'quadrant': 'D',
    'regime_label': 'Stagflation/Hike Regime — Fed Held but Dec Hike Odds at 82.6%, Sep Inflation Reaccelerated, AI Sector Rotation Hit Satellite Tech Names',
    'confidence': 'high',   # Rates leg: Oct28 hold was itself hawkish (2 dissents WANTED a hike), Dec hike odds now 82.6% (up from 78.3%) — strongest hike conviction this cycle. BS leg: flat $6.75T, still ~$250B under $7T. Both conditions still confirm D firmly
    'fed_funds_rate': '3.75-4.00% (held at Oct 28 FOMC, 10-2 — Hammack & Cook dissented FOR a hike, a hawkish-leaning hold); next meeting Dec; CME FedWatch Dec hike probability 82.6% (up from 78.3% the day prior) — highest conviction yet',
    'fed_balance_sheet': '$6.748-6.75T total assets (H.4.1, wk of Nov 4); +2.4% YoY, up slightly from $6.746T (Oct 28) — still flat, not expanding; ~$250B below $7T QB trigger',
    'pce_headline': '3.6% YoY (Sep print, released Oct 29) — up from Aug\'s 3.4%, reaccelerated; +0.5% MoM, driven by an energy cost surge (consistent with Oct\'s Brent spike)',
    'pce_core': '3.1% YoY (Sep print) — up from Aug\'s 3.0%; the Aug cooling was temporary, Sep reversed higher, explaining both the Sep hike and the now-elevated Dec hike odds',
    'cpi_latest': '3.7% YoY headline (Sep print) — hottest reading this cycle, consistent with the PCE reacceleration',
    'jobs_may': 'Sep payrolls badly missed: +29K vs ~85K consensus, unemployment 4.2%, Jul/Aug revised down a combined 60K — labor weakening even as inflation reaccelerated and Dec hike odds rose; this divergence (weak jobs + hot inflation + hike-lean Fed) is the clearest stagflation signature yet',
    'yield_curve': '10Y 5.00% / 2Y 4.69% (Oct 23, latest sourced) ~= +31bp — narrower than early Oct\'s +44bp; re-verify next cycle given the Nov 5 vol spike likely moved both legs',
    'vix': 'Spiked to 28.09 intraday (Nov 5, 7-month high) on the AI-stock selloff, moderated to 25.64 (Nov 6, -9.0%) — the first genuine volatility event this cycle, breaking the prior months\' low-VIX/high-geopolitical-risk complacency pattern. Still below the 35 emergency-protocol threshold',
    'brent': 'Violent round trip: spiked above $110 (Nov 3) then crashed >13% in a week to below $98 (Nov 6), steepest weekly decline since March 2020, on hopes of a Middle East diplomatic breakthrough — a real de-escalation signal for once, though Iran\'s official position (strait closed until US accepts terms) hasn\'t changed, so treat the price move as hope, not confirmed resolution',
    'fedwatch_next_meeting': 'Oct 28 FOMC: HELD 3.75-4.00%, 10-2 vote, 2 dissents (Hammack, Cook) wanted a hike — a hawkish hold, not a dovish one',
    'fedwatch_dec_cumulative': 'Dec FOMC hike probability 82.6% (CME FedWatch, up from 78.3% the day before) — the clearest single-direction read all cycle, reinforced by the Sep inflation reacceleration',
    'hormuz_status': 'Still officially CLOSED — Iran\'s Armed Forces say the strait stays shut until the US accepts Tehran\'s conditions; US Navy mine-clearing ongoing (100+ suspected mines found by underwater drones); Oman rescued 25 sailors from a burning tanker in the strait in late Oct. Brent\'s Nov 6 crash reflects market hope for a breakthrough, not an actual change in Iran\'s stated position — don\'t conflate the two',
    'tariff_section_122': 'EXPIRED Jul 24, 2026 — replaced by Section 301 duties (10-12.5%, ~80 economies). No change this cycle',
    'mas_stance': 'Oct 14 review: held all 3 NEER band params unchanged (2nd consecutive pause after Apr/Jul tightenings) — narrowed 2026 core inflation forecast to 1.5-2% from 1.5-2.5%',
    'open_inflections': [
        'AI sector rotation — Nov 3 midterm ballot measures rejected AI data centers in 40/41 local votes, triggering a Nov 5 selloff: NVDA -9.3% ($181.60), TSM -10.8% ($353.10), GOOG -2.2% ($282.57), Philly Semi Index -12%. Characterized as a ~$70B hedge-fund deleveraging event (Jordi Visser), not a fundamental AI bubble pop — money rotating into industrials/banks/energy/"AI landlords," not exiting markets. Directly relevant to this book\'s GOOG/NVDA/TSM exposure',
        'Dec hike odds at 82.6%, highest conviction this cycle, driven by Sep PCE/CPI reacceleration (3.6%/3.1%, 3.7% CPI) — the hike case just got stronger, not weaker',
        'VIX\'s first real spike this cycle (28.09 intraday Nov 5) — the long-running calm-despite-chaos divergence finally broke; watch whether this normalizes or becomes a new higher-vol regime',
        'Brent\'s >13% weekly crash (Nov 6) is a hope-driven move, not a confirmed Hormuz resolution — Iran\'s official stance is unchanged; don\'t treat the price action as the geopolitical risk having resolved',
        'Sep payrolls badly missed (+29K) + inflation reaccelerating simultaneously — the clearest stagflation signature yet this cycle',
        'MAS held for 2nd straight review (Oct 14), in contrast to the Fed\'s hike-lean path — policy divergence worth tracking for SGD',
    ],
    'quadrant_b_distance': 'far',
}

# ============================================================
# REGIME PLAYBOOK — drives Core-Bond duration target
# ============================================================
REGIME_PLAYBOOK = {
    'Stagflation': {
        'bond_duration_target': 3.0,   # years, max
        'bond_sleeve': {'SHY': 0.30, 'VTIP': 0.25, 'BND': 0.35, 'IEF': 0.10, 'SPTL': 0.00},
    },
    'Growth/LowInflation': {
        'bond_duration_target': 6.0,
        'bond_sleeve': {'BND': 0.50, 'IEF': 0.30, 'SPTL': 0.20},
    },
    'Recession/Deflation': {
        'bond_duration_target': 10.0,
        'bond_sleeve': {'SPTL': 0.40, 'IEF': 0.35, 'BND': 0.25},
    },
    'Risk-Off/Transition': {
        'bond_duration_target': 4.0,
        'bond_sleeve': {'SHY': 0.40, 'BND': 0.35, 'IEF': 0.25},
    },
}

# ============================================================
# MONTHLY CONTRIBUTIONS (SGD → USD at 0.79)
# ============================================================
# satellite_sgd moved to config/settings_satellite.py
MONTHLY_CONTRIB = {
    'core_sgd': 2000,
    'fx_rate': 0.79,
}

# ============================================================
# OUTPUT CONFIG
# ============================================================
OUTPUT_PATH = 'output/portfolio_tracker.xlsx'
NAS_PATH = '/volume1/investments/portfolio_tracker.xlsx'
SNAPSHOT_PATH = 'output/latest_snapshot.json'
DASHBOARD_PATH = 'output/dashboard.html'
NAV_HISTORY_PATH = 'output/nav_history_core.json'

# ============================================================
# SNAPSHOT DATE
# ============================================================
SNAPSHOT_DATE = '2026-11-09'

# ============================================================
# DATA FRESHNESS METADATA
# ============================================================
# Bump 'value' (YYYY-MM-DD) every time you actually refresh the underlying data.
# The audit module compares each entry to today and flags STALE if older than cadence_days.
DATA_FRESHNESS = {
    'snapshot_date': {
        'value':         SNAPSHOT_DATE,
        'cadence_days':  14,
        'label':         'Holdings snapshot',
        'update_action': 'Run main.py (any mode); bump SNAPSHOT_DATE to today',
    },
    'macro_regime': {
        'value':         '2026-11-09',
        'cadence_days':  7,
        'label':         'Macro regime block',
        'update_action': 'Update MACRO_REGIME dict + open_inflections in settings.py; bump value here',
    },
    'offline_prices': {
        'value':         SNAPSHOT_DATE,
        'cadence_days':  14,
        'label':         'extract_offline() prices',
        'update_action': 'Run main.py --yf-only or --hybrid; SNAPSHOT_DATE auto-syncs',
    },
    'ibkr_manual_positions': {
        'value':         '2026-11-09',
        'cadence_days':  14,
        'label':         'IBKR manual positions (API locked, IBKR Lite)',
        'update_action': 'Re-check IBKR app/web positions screen; update IBKR_MANUAL_POSITIONS dict',
    },
}

# ============================================================
# WATCHLIST — empty. Core/Core-Plus is passive index exposure; there are no
# active entry/exit theses to track here. All watchlist items moved to
# config/settings_satellite.py.
# ============================================================
WATCHLIST = {}

# ============================================================
# WATCHLIST REGIME FIT — empty for the same reason as WATCHLIST above.
# ============================================================
WATCHLIST_REGIME_FIT = {}
