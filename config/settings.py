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
    'as_of_date': '2026-08-29',
    'quadrant': 'D',
    'regime_label': 'Stagflation / Hike-Risk — Hormuz Closed, Ceasefire Collapsed; Inflation Cooling but Still Elevated',
    'confidence': 'high',   # High rates confirmed (Jul 29 hold, not cut) + low/declining BS ($6.73T, well under $7T) both hold D; geopolitical leg deteriorated (closure, not pause) while inflation improved — net still D
    'fed_funds_rate': '3.50–3.75% (held Jul 29 FOMC, 9-3 vote, 3 dissents wanted hike); next meeting Sep 16, 2026',
    'fed_balance_sheet': '$6.73T total assets (H.4.1, wk of Aug 26); down slightly wk/wk (-$20B) from $6.75T; ~$270B below $7T QB trigger',
    'pce_headline': '3.7% YoY (June print, released Jul 30) — down from May 4.1%; MoM -0.1%',
    'pce_core': '3.3% YoY (June print) — down from May 3.4%; MoM +0.1%; still well above 2% target',
    'cpi_latest': '3.5% YoY headline (June print, released Jul 14); prior May print 4.2%/2.9% core',
    'jobs_may': "June payrolls +57k (vs 115k consensus), well below May's downwardly-revised +129k; unemployment 4.2% (participation fell to 61.5%, lowest since Mar 2021) — soft print despite hot inflation; weak July print (per Aug 7 reporting) further deflated Fed hike odds",
    'yield_curve': '10Y 4.68% / 2Y 4.24% (Aug 27) ≈ +44bp; positive, roughly stable',
    'vix': '14.57 (Aug 29) — 2026 low, falling further from Jul 28\'s 17.57; no breach 25/35, market pricing calm despite active Hormuz conflict',
    'brent': 'Sharp decline: $87.46 (Aug 27, intraday +1.97% to $89.13) down from $95.29 (Aug 21) and $94.12 (Aug 24) — war premium unwinding through the month even as the strait itself remains closed, a notable divergence between spot price and ground conflict',
    'fedwatch_next_meeting': 'Sep 16 FOMC: readings diverging hard across sources as of Aug 25-28 — CME FedWatch as low as 45.1% hold / ~30% hike, other trackers 58-60% hold, prediction markets ~51% hold; a "hike now expected" narrative (Chase/Goldman coverage) has emerged citing energy-shock inflation pass-through, in tension with the weak-jobs-driven hold case from a week prior — no consensus reading exists this cycle',
    'fedwatch_dec_cumulative': 'No clean read this cycle — conflicting signals: fed funds futures broadly price a year-end hike lean (~4%) per some sources, while Sep-specific odds favor hold post jobs-miss; genuinely mixed, re-verify next cycle',
    'hormuz_status': 'CLOSED/CONTESTED but with a live diplomatic track — Iran established a "Persian Gulf Strait Authority" (May) requiring passage permits, periodic attacks/US retaliation disrupted traffic for ~5 months; conflict abated in early Aug amid Iran-Oman talks, with Iran-Oman now floating a temporary shipping-corridor proposal and Qatar\'s PM visiting Tehran to mediate a return to pre-Feb-28 status quo; simultaneously Iran is warning of ship seizures ahead of a Bessent-led US sanctions push and pushing back on Trump\'s "economic D-Day" threat — de-escalation talks and fresh threats running in parallel, unresolved',
    'tariff_section_122': 'Federal Circuit administrative stay (issued May 12) still in force "until further notice"; no ruling found on the stay-pending-appeal motion as of late Aug — unresolved, unchanged since Jul 28',
    'mas_stance': 'Unchanged since Jul 27 statement (2nd consecutive tightening step, smaller than April; S$NEER holding upper half of band); next quarterly statement due ~Oct 2026',
    'open_inflections': [
        'Hormuz: Iran-Oman shipping-corridor proposal + Qatar mediation vs. Iran ship-seizure warnings/Bessent sanctions push — watch which track wins next',
        'Iran-Israel-US ceasefire lapsed mid-Aug; Israel struck Lebanon Aug 16; Kushner regional diplomacy ongoing but no Iran breakthrough',
        'VIX at 2026 low (14.57) despite active Hormuz conflict — complacency/divergence risk, could reprice sharply on any escalation headline',
        'Sep 16 FOMC — no consensus read (45-60% hold across sources); a hike-now-expected narrative has emerged, contradicting last week\'s jobs-miss-driven hold case',
        'Dec 2026 rate path genuinely unclear — hike-lean futures pricing vs jobs-miss-driven hold odds conflict, needs a clean re-read next cycle',
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
SNAPSHOT_DATE = '2026-08-29'

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
        'value':         '2026-08-29',
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
