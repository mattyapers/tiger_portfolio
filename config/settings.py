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
    'as_of_date': '2026-09-14',
    'quadrant': 'D',
    'regime_label': 'Stagflation / Hike-Risk — Hormuz Escalating (Vessel Struck), Ceasefire Dead; Inflation Improving but Rate Path Hawkish',
    'confidence': 'high',   # BS flat ~$6.7T well under $7T holds D; rate-path risk flipped from cut-lean to hike-lean (Warsh Jackson Hole) pushes further from B, not toward it; Hormuz escalation (vessel struck Sep 13) reinforces stagflation leg via Brent spike
    'fed_funds_rate': '3.50–3.75% (held since Jul 29 FOMC); Sep 16, 2026 FOMC decision pending — this read predates the outcome',
    'fed_balance_sheet': '$6.70T total assets (H.4.1, wk of Sep 2); +$6B w/w, +$135B YoY — flat, not expanding; ~$300B below $7T QB trigger',
    'pce_headline': '3.7% YoY (Jul print, released Aug 26) — latest available; Aug print due Sep 30',
    'pce_core': '3.3% YoY (Jul print) — latest available; Aug CPI (Sep 11) improved to 3.35% headline / 2.45% core YoY, a positive lead into Sep 30 PCE',
    'cpi_latest': '3.35% YoY headline / 2.45% core (Aug print, released Sep 11) — improved from Jul\'s 3.5%/3.3% PCE-adjacent reads',
    'jobs_may': "No new print sourced this cycle; carried from last cycle — June payrolls +57k (vs 115k consensus), unemployment 4.2%; weak July print (per Aug 7 reporting) had deflated hike odds, since reversed by Warsh's hawkish Jackson Hole speech",
    'yield_curve': '10Y 4.96% / 2Y 4.63% (Sep 11) ≈ +33bp; positive but narrower than Aug 27\'s +44bp — both legs shifted up ~30bp',
    'vix': '16.34 (mid-Sep) — up from Aug 29\'s 14.57 2026-low but still in normal 15-25 band; no breach 25/35',
    'brent': 'Sharp reversal higher: ~$102-104 (Sep 12-14), up from $87.46 (Aug 27) — renewed U.S.-Iran tit-for-tat strikes reignited war premium; opposite direction from last cycle\'s unwind',
    'fedwatch_next_meeting': 'Sep 16 FOMC: hike-risk surged — Aug 31 CME read ~66% hike, a sharp reversal from Aug 29\'s 67.6% hold-lean, driven by Warsh\'s hawkish Jackson Hole speech; live/unresolved into the decision',
    'fedwatch_dec_cumulative': 'CME FedWatch (Sep read): ~78.2% hold / 15.4% cut / 5.4% hike through Dec — calmer than the Sep meeting read implies; Sep hike-risk currently looks front-loaded rather than sustained into Dec, an internal inconsistency worth re-checking once the Sep 16 outcome lands',
    'hormuz_status': 'CLOSED, Day 197, traffic ~90% below pre-conflict (5-11 ships/day vs ~125 normal) — escalated since last cycle: Iran reports a commercial vessel struck near Qeshm (Sep 13), and the planned Gulf-Iran talks on Oman\'s reopening plan were postponed indefinitely the same day. Reverses last cycle\'s cautious de-escalation read',
    'tariff_section_122': 'Unchanged — Federal Circuit administrative stay (issued May 12) still in force pending appeal; no ruling found as of Sep 14, now stale since May',
    'mas_stance': 'Unchanged since Jul 27 statement (S$NEER upper half of appreciating band); next quarterly statement due ~Oct 2026',
    'open_inflections': [
        'Sep 16 FOMC decision — live, hike-risk surged since Aug 29 (Warsh Jackson Hole speech); outcome will force a regime re-read next cycle regardless of direction',
        'Hormuz escalation: vessel struck Sep 13 + Gulf-Iran talks postponed same day — track reversed from de-escalation to escalation since last cycle',
        'Brent +17% in ~3 weeks ($87→$102) — war premium back in full; watch pass-through into next PCE/CPI prints',
        'Iran-Israel-US: no ceasefire in force, Trump warning harsher retaliation if Iran strikes again — situation hardened, not softened, since Aug',
        'Aug PCE release Sep 30 — first read testing whether Aug CPI\'s improvement (3.35%/2.45%) carries through to the Fed\'s preferred gauge',
        'Section 122 tariff Federal Circuit stay unresolved since May — appeal outcome still pending',
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
SNAPSHOT_DATE = '2026-09-14'

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
        'value':         '2026-09-14',
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
