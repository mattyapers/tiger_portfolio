"""
settings.py — Single source of truth for portfolio rules and API config.

Credentials (TIGER_ID, ACCOUNT, PRIVATE_KEY_PATH, LICENSE) are loaded from .env
via python-dotenv. The .env file is gitignored. See .env.example for the schema.
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
# PORTFOLIO STRUCTURE — 68/11/21 allocation
# ============================================================
# Core split: Core (equity) + Core-Bond (fixed income) = 68% total
TIER_TARGETS = {
    'Core': 0.68,
    'Core-Plus': 0.11,
    'Satellite': 0.21,
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
    # 'MSFT': 'Satellite',  # WATCHLIST — uncomment when entry conditions met post-2026-04-29
    'SPYD': 'Core-Plus',
    'ONEQ': 'Core-Plus',
    'GLDM': 'Satellite',
    'GOOG': 'Satellite',
    'RTX':  'Satellite',
    'NVDA': 'Satellite',
    'TSM':  'Satellite',
    'AAPL': 'Satellite',
    'MA':   'Satellite',
    'CAT':  'Satellite',
    'KO':   'Satellite',
    'BABA': 'Satellite',
    'AON':  'Satellite',
    'XLE':  'Satellite',
    'COP':  'Satellite',   # ConocoPhillips — energy/stagflation thesis
    'NTR':  'Satellite',   # Nutrien — potash/commodity/food security
}

# ============================================================
# TIER DEFINITIONS — Conviction-weighted satellite positioning
# ============================================================
# Tier-1 (12-15%): Highest conviction, regime-aligned, multi-year hold
#   → GLDM (inflation hedge), RTX (defense), GOOG (AI/Cloud compounder)
# Standard (7%): Thesis-driven, full satellite allocation
#   → NVDA, TSM, AAPL, MA, CAT, AON
# Reduced (4-5%): Held with lower conviction or partial thesis conflict
#   → KO (dividend only, no growth edge), BABA (deglobalization conflict)
# Unallocated buffer: 7% — reserved for opportunistic entries (e.g. MSFT)
# ============================================================
SATELLITE_TARGETS = {
    'GLDM': 0.15,   # Tier-1 — Defensive hedge, stagflation + geopolitical
    'RTX':  0.15,   # Tier-1 — Defense theme, NATO spending catalyst
    'GOOG': 0.12,   # Tier-1 — AI + Cloud growth compounder (upgraded from 7%)
    'NVDA': 0.07,   # Standard — AI infrastructure
    'TSM':  0.07,   # Standard — Semiconductor / deglobalization thesis
    'AAPL': 0.07,   # Standard — Consumer tech
    'MA':   0.07,   # Standard — Payments / cashless economy
    'CAT':  0.05,   # Reduced — P/E elevated (41x vs 19x avg); hold but cap until reversion
    'AON':  0.07,   # Standard — Risk management / insurance
    'KO':   0.03,   # Reduced — Defensive dividend, trim to make room
    'BABA': 0.01,   # Minimum — Deglobalization conflict, hold/exit candidate
    'XLE':  0.07,   # Standard — Energy hedge, stagflation alpha
    'COP':  0.04,   # Small — ConocoPhillips opportunistic, stagflation energy
    'NTR':  0.03,   # Small — Nutrien potash, food security / commodity
}
# Sum = 1.00 — fully allocated (COP/NTR fill former MSFT buffer slot)
_target_sum = sum(SATELLITE_TARGETS.values())
assert abs(_target_sum - 1.00) < 0.01, \
    f"SATELLITE_TARGETS sum {_target_sum:.2f} != 1.00 — check tier allocations"

# ============================================================
# REBALANCING RULES
# ============================================================
REBALANCE_RULES = {
    'drift_threshold': 0.03,
    'max_position_pct': 0.15,    # Raised: Tier-1 positions (GLDM, RTX, GOOG) may hold 12-15%
    'review_cycle_days': 14,
    'correlation_target': 0.50,
    'correlation_max': 0.75,
}

# ============================================================
# ENTRY / EXIT SIGNALS
# ============================================================
SIGNAL_RULES = {
    'pe_max': 30,
    'pe_premium_trim': 0.25,
    'stop_loss_pct': -0.15,
    'take_profit_pct': 1.00,
}

# ============================================================
# 5-YEAR AVERAGE P/E RATIOS (updated March 2026)
# ============================================================
PE_5Y_AVERAGES = {
    'GOOG': 25.0,
    'RTX':  22.0,
    'NVDA': 55.0,
    'TSM':  22.0,
    'AAPL': 28.0,
    'MA':   36.0,
    'CAT':  19.0,
    'KO':   24.0,
    'BABA': 15.0,
    'AON':  25.0,
    'COP':  13.0,   # Energy cyclical — 5Y avg depressed by 2020 crash
    'NTR':  14.0,   # Potash/fertilizer — commodity cycle average
}

# ============================================================
# MACRO REGIME — Updated 2026-05-05
# ============================================================
MACRO_REGIME = {
    'as_of_date': '2026-05-05',
    'quadrant': 'D',
    'regime_label': 'Stagflation-Lite + Energy Shock Persistent (Hormuz limbo)',
    'confidence': 'high',
    'fed_funds_rate': '3.50–3.75% (held Apr 29, third consecutive)',
    'fed_balance_sheet': '$6.7T as of Apr 23, contracting (-$7B WoW, -$9B YoY)',
    'pce_headline': '3.5% YoY (March print, released Apr 30)',
    'pce_core': '3.2% YoY (March print, released Apr 30)',
    'yield_curve': '10Y 4.39% / 2Y 3.88% = +51bp (modestly positive, flatter than historical average)',
    'vix': '16.78 (May 3); -38% over 30d, risk-on complacent',
    'brent': '$108.17/bbl (May 3); ~$108-111 weekly range',
    'fedwatch_next_meeting': 'June 16-17 FOMC: ~70% hold / ~28% cut',
    'fedwatch_dec_cumulative': 'NEEDS INPUT — Fed dot plot signals 1 cut penciled for 2026; swaps markets show mixed near-zero implied cut by some measures',
    'hormuz_status': 'Effectively closed — Iran declared open Apr 17, US blockade continues, shipping -90%',
    'tariff_section_122': 'Active 15% global (effective Feb 24); expires Jul 24, 2026; CIT challenge filed Mar 5 by 24 states; admin planning Section 301/232 replacements',
    'mas_stance': 'Tightened Apr 14, 2026 — slight increase in S$NEER appreciation slope (first tightening since 2022); SGD tailwind for USD-asset holders',
    'open_inflections': [
        'Strait of Hormuz reopening — Iran says open, US blockade continues, oil pricing the gap',
        'Powell→Warsh handover — Apr 29 reportedly Powell\'s final FOMC; Warsh policy stance unconfirmed',
        'June 16-17 FOMC — first decision likely under new chair; FedWatch ~28% cut',
        'Iran ceasefire violations — both sides accuse small-scale attacks; re-escalation risk',
        'Section 122 tariff expiry Jul 24 — Congressional extension unlikely; Section 301/232 replacement timing TBD',
    ],
    'quadrant_b_distance': 'far',
}

# ============================================================
# REGIME PLAYBOOK — drives bond duration + satellite overrides
# ============================================================
REGIME_PLAYBOOK = {
    'Stagflation': {
        'bond_duration_target': 3.0,   # years, max
        'bond_sleeve': {'SHY': 0.30, 'VTIP': 0.25, 'BND': 0.35, 'IEF': 0.10, 'SPTL': 0.00},
        'satellite_overrides': {'GLDM': 0.22, 'RTX': 0.18, 'KO': 0.10, 'NVDA': 0.05},
    },
    'Growth/LowInflation': {
        'bond_duration_target': 6.0,
        'bond_sleeve': {'BND': 0.50, 'IEF': 0.30, 'SPTL': 0.20},
        'satellite_overrides': {},
    },
    'Recession/Deflation': {
        'bond_duration_target': 10.0,
        'bond_sleeve': {'SPTL': 0.40, 'IEF': 0.35, 'BND': 0.25},
        'satellite_overrides': {'GLDM': 0.15},
    },
    'Risk-Off/Transition': {
        'bond_duration_target': 4.0,
        'bond_sleeve': {'SHY': 0.40, 'BND': 0.35, 'IEF': 0.25},
        'satellite_overrides': {'GLDM': 0.20},
    },
}

# ============================================================
# MONTHLY CONTRIBUTIONS (SGD → USD at 0.79)
# ============================================================
MONTHLY_CONTRIB = {
    'core_sgd': 2000,
    'satellite_sgd': 300,
    'fx_rate': 0.79,
}

# ============================================================
# OUTPUT CONFIG
# ============================================================
OUTPUT_PATH = 'output/portfolio_tracker.xlsx'
NAS_PATH = '/volume1/investments/portfolio_tracker.xlsx'

# ============================================================
# SNAPSHOT DATE
# ============================================================
SNAPSHOT_DATE = '2026-05-05'

# ============================================================
# DATA FRESHNESS METADATA
# ============================================================
# Bump 'value' (YYYY-MM-DD) every time you actually refresh the underlying data.
# The audit module compares each entry to today and flags STALE if older than cadence_days.
DATA_FRESHNESS = {
    # key: {value: last-updated date, cadence_days: max acceptable age, label: display name, update_action: exact thing to do}
    'snapshot_date': {
        'value':         SNAPSHOT_DATE,
        'cadence_days':  14,
        'label':         'Holdings snapshot',
        'update_action': 'Run main.py (any mode); bump SNAPSHOT_DATE to today',
    },
    'macro_regime': {
        'value':         '2026-05-05',
        'cadence_days':  7,
        'label':         'Macro regime block',
        'update_action': 'Update MACRO_REGIME dict + open_inflections in settings.py; bump value here',
    },
    'pe_5y_averages': {
        'value':         '2026-03-30',
        'cadence_days':  90,
        'label':         '5Y P/E averages (quarterly)',
        'update_action': 'Refresh PE_5Y_AVERAGES from Macrotrends/YF; bump value here',
    },
    'satellite_targets': {
        'value':         '2026-04-17',
        'cadence_days':  30,
        'label':         'Satellite tier weights',
        'update_action': 'Review SATELLITE_TARGETS for post-trade changes; bump value here',
    },
    'watchlist': {
        'value':         '2026-05-05',
        'cadence_days':  14,
        'label':         'Watchlist pending actions',
        'update_action': 'Resolve or extend each WATCHLIST entry; bump value here',
    },
    'offline_prices': {
        'value':         SNAPSHOT_DATE,
        'cadence_days':  14,
        'label':         'extract_offline() prices',
        'update_action': 'Run main.py --yf-only or --hybrid; SNAPSHOT_DATE auto-syncs',
    },
}

# ============================================================
# WATCHLIST
# ============================================================
WATCHLIST = {
    'BABA_EXIT': {
        'ticker': 'BABA',
        'action': 'EXIT',
        'note': (
            'STOP-LOSS TRIGGERED: -15.8% loss ($138.59 vs $164.69 cost). '
            'Override log (2026-03-31): "No further overrides on BABA. '
            'Next breach of -15% from current price = execute exit, no exceptions." '
            'Sell 1 share (~$138 proceeds). Redeploy into GLDM (underweight) or AON (score 1 entry). '
            'After execution: remove BABA from TICKER_TIERS and SATELLITE_TARGETS.'
        ),
        'trigger_date': '2026-04-18',
    },
    'XLE_DEFERRED': {
        'ticker': 'XLE',
        'action': 'DEFER',
        'note': (
            'Original thesis: stagflation + oil >$100 = energy alpha. '
            'Oil dropped to $88 on Iran ceasefire (Apr 8). Thesis weakened. '
            'Entry condition: oil spikes back above $95 after ceasefire collapses (watch Apr 21). '
            'Skip condition: ceasefire converts to deal and oil settles below $85 — '
            'redirect May tranche ($200) to GLDM or AON instead. '
            'NOTE: XLE at 0.07 target with no position will generate ADD signals — expected, ignore until resolved.'
        ),
        'review_date': '2026-04-21',
    },
    'CAT_TRIM': {
        'ticker': 'CAT',
        'action': 'TRIM 50%',
        'note': (
            'P/E 41x vs 19x 5Y avg (116% premium). Score 5 — both trim triggers firing. '
            'Override on 2026-03-31 was correct (+$80/share gain). '
            'Recommend trimming 50% at current levels ($773+). '
            'Proceeds ($94 est.) → AON or MA. Re-entry target: $580.'
        ),
    },
    'CAT_REENTRY': {
        'ticker': 'CAT',
        'target_price': 580,
        'note': 'Re-entry after trim — Infrastructure supercycle thesis intact',
    },
    'MSFT_WATCH': {
        'ticker': 'MSFT',
        'target_price': 380,
        'note': (
            'DO NOT initiate before April 29, 2026 Q3 earnings. '
            'Entry requires: Azure Q3 growth >= 38%, '
            'CapEx guidance plateaus, stock holds above $380 post-earnings, '
            'no adverse OpenAI lawsuit outcome. Target 5-7% satellite if met.'
        ),
        'catalyst_date': '2026-04-29',
        'entry_condition': 'Azure >= 38% AND stock > $380 post-earnings AND no lawsuit shock',
    },
    'LMT': {
        'ticker': 'LMT',
        'target_price': 480,
        'note': 'Defense alternative to RTX',
    },
    'EUAD': {
        'ticker': 'EUAD',
        'target_price': None,
        'note': 'European defense ETF — NATO rearmament',
    },
    'DBS': {
        'ticker': 'DBS',
        'target_price': None,
        'note': 'Singapore bank — SGD base, ASEAN growth',
    },
    'COPX': {
        'ticker': 'COPX',
        'target_price': None,
        'note': 'Copper miners — critical minerals theme',
    },
    # Quadrant B rotation candidates — DO NOT enter yet. Monitor for Fed BS > $7T + cut prob > 30%.
    'QB_ISRG':  {'ticker': 'ISRG',  'action': 'WATCH', 'note': 'Quadrant B candidate — surgical robotics growth'},
    'QB_APD':   {'ticker': 'APD',   'action': 'WATCH', 'note': 'Quadrant B candidate — industrial gases / green hydrogen'},
    'QB_FCX':   {'ticker': 'FCX',   'action': 'WATCH', 'note': 'Quadrant B candidate — copper / critical minerals'},
    'QB_CCJ':   {'ticker': 'CCJ',   'action': 'WATCH', 'note': 'Quadrant B candidate — uranium / nuclear renaissance'},
}