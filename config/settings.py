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
    'as_of_date': '2026-07-28',
    'quadrant': 'D',
    'regime_label': 'Stagflation / Hike-Risk Elevated — Hormuz Ceasefire-Pause Fraying the Oil-Shock Narrative',
    'confidence': 'high',   # Underlying inflation (MAS tightening, still-rising hike odds) still confirms D; the new fact this cycle is a de-escalation, not a reversal
    'fed_funds_rate': '3.50–3.75% (held since Dec 2025 cut); Jul 29 FOMC decision tomorrow',
    'fed_balance_sheet': '$6.72-6.74T total assets (H.4.1, wk of Jul 22); ~$260-280B below $7T QB trigger; roughly flat (+$4B wk, +$89B YoY)',
    'pce_headline': 'June print due Jul 30, 2026 (not yet released); Truflation nowcast ~3.7% YoY, flat MoM',
    'pce_core': 'June print due Jul 30, 2026 (not yet released); Truflation nowcast +0.2% MoM / ~3.3% YoY — still elevated',
    'cpi_latest': '3.5% YoY headline (June print, released Jul 14); prior May print 4.2%/2.9% core',
    'jobs_may': "June payrolls +57k (vs 115k consensus), well below May's downwardly-revised +129k; unemployment 4.2% (participation fell to 61.5%, lowest since Mar 2021) — soft print despite hot inflation",
    'yield_curve': '10Y ~4.67% (Jul 25) / 2Y ~4.21% (Jul 10, STALE — re-verify) ≈ +46bp; positive',
    'vix': '17.57, -5.44% (Jul 28) — falling, unwinding the Jul 23 spike as Hormuz tensions ease',
    'brent': 'Sharp reversal: spot fell to $82.62 (Jul 27, -8.68% single day) on US-Iran attack pause + Oman-mediated reopening talks; futures still quoting $96-100 range, pricing a lingering risk premium the spot move hasn\'t confirmed — divergence worth watching, not yet resolved',
    'fedwatch_next_meeting': 'Jul 29 FOMC: 61.3% hold / 38.7% hike probability (Jul 25) — still climbing despite the oil de-escalation (up from 34.7% a week ago, 10.7% two weeks ago); looks like a lagging reaction to the pre-ceasefire inflation data, not yet reflecting Jul 26-27 news',
    'fedwatch_dec_cumulative': 'No fresh read this cycle — carry-forward ~78.2% no-change / ~15.4% cut / ~5.4% hike cumulative to Dec 2026 is now STALE, re-verify next cycle',
    'hormuz_status': 'CEASEFIRE-PAUSE (Jul 26) — US and Iran paused attacks after the Jul 11-23 escalation; Oman-mediated talks resumed on reopening. Traffic still far below normal (24-vessel backlog at Kharg Island as of Jul 26-27). First de-escalation signal since the closure, but durability unconfirmed — the prior Jun 17 agreement collapsed within weeks, so treat this as fragile, not resolved.',
    'tariff_section_122': 'Statutory Section 122 duties expired Jul 24 as scheduled; Federal Circuit appeal on the merits still pending (stay granted Jun 11), no ruling yet — unresolved',
    'mas_stance': 'RESOLVED Jul 27: 2nd consecutive quarter of SGD-appreciation-slope tightening (smaller step than April); Q2 core inflation 1.5% YoY (up from 1.2% pre-conflict); Q2 GDP +5.7% YoY (beat); inflation seen elevated into early 2027',
    'open_inflections': [
        'Hormuz ceasefire-pause (Jul 26) — durability unconfirmed, watch for re-escalation (prior Jun 17 truce collapsed within weeks) or a genuine reopening',
        'Jul 29 FOMC — 38.7% hike probability, highest of this cycle, still rising despite the oil de-escalation (lagging reaction, needs next reading to confirm/deny)',
        'June PCE due Jul 30 — will confirm/deny Truflation nowcast (3.7% headline / 3.3% core)',
        'Section 122 tariff appeal still unresolved at Federal Circuit post-expiry',
        '2Y yield reading is stale (Jul 10) — re-verify before trusting the curve reading next cycle',
        'Fed BS vs $7T + Dec cut prob vs 30% — Quadrant B rotation trigger, still far (~$260-280B / cut-prob reading itself stale)',
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
SNAPSHOT_DATE = '2026-07-24'

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
        'value':         '2026-07-28',
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
