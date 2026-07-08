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
# MACRO REGIME — Updated 2026-06-06
# ============================================================
MACRO_REGIME = {
    'as_of_date': '2026-07-08',
    'quadrant': 'D',
    'regime_label': 'Stagflation-Lite / Hike-Risk, Geopolitical Escalation Re-Igniting (Hormuz ceasefire fraying)',
    'confidence': 'medium',
    'fed_funds_rate': '3.50–3.75% (held since Dec 2025 cut); July 28-29 FOMC: 73.4% hold probability (Jul 7 print)',
    'fed_balance_sheet': '$6.736T total assets (H.4.1, wk of Jun 24, released Jul 2); $264B below $7T QB trigger; roughly flat',
    'pce_headline': '4.07% YoY (May print, released Jun 25) — accelerating',
    'pce_core': '3.41% YoY (May print) — highest since Oct 2023',
    'cpi_latest': '4.2% YoY headline / 2.9% core (May print, released Jun 10); energy +23.5% YoY, gasoline +40.5%; June print due Jul 14',
    'jobs_may': "June payrolls +57k (vs 115k consensus), well below May's downwardly-revised +129k; unemployment 4.2% (participation fell to 61.5%, lowest since Mar 2021) — soft print despite hot inflation",
    'yield_curve': '10Y 4.49% / 2Y 4.14% (Jul 2 close) = +35bp; positive, roughly stable vs prior weeks',
    'vix': '16.36, +5.07% (Jul 8) — no breach of 25/35 despite active Hormuz conflict; lagging the geopolitical news flow',
    'brent': '$77.92/bbl, +5.06% on the day (Jul 8) on Hormuz tanker attacks + US revoking Iran oil waiver',
    'fedwatch_next_meeting': 'July 28-29 FOMC: 73.4% hold probability (Jul 7 print)',
    'fedwatch_dec_cumulative': '~78.2% no-change / ~15.4% cut / ~5.4% hike cumulative to Dec 2026 (approximate/illustrative pricing)',
    'hormuz_status': 'Contested/reopening — Iran struck 3 ships Jul 6-7; US hit 80+ targets in response Jul 7-8; traffic resilient (108 crossings over the weekend) vs 120-140/day pre-war baseline',
    'tariff_section_122': 'CIT struck down 10% surcharge May 7 (2-1); Federal Circuit stayed ruling Jun 11 pending appeal; tariff still collected; statutory expiry ~Jul 23-24, 2026',
    'mas_stance': 'Last statement Apr 14 — slightly steeper S$NEER appreciation slope on inflation concerns; next quarterly statement due Jul 2026, not yet released as of Jul 8',
    'open_inflections': [
        'US-Iran ceasefire (Islamabad MOU, signed Jun 17) declared "over" by Trump Jul 8 after mutual strikes — watch for formal collapse vs. talks continuing',
        'Fed balance sheet vs $7T + Dec cut prob vs 30% — Quadrant B rotation trigger, currently $264B / ~15pp away',
        'Section 122 tariff appeal outcome before Jul 23-24 statutory expiry',
        'VIX/Brent repricing lag — equity vol has not yet reflected the Jul 6-8 Hormuz escalation; a catch-up spike could raise regime confidence to High',
        'MAS July quarterly policy statement — due but not yet released',
        'June CPI print due Jul 14 — hot read would reinforce hike-risk/D regime lock-in',
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
SNAPSHOT_DATE = '2026-07-08'

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
        'value':         '2026-07-08',
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
    'MRVL': {
        'ticker': 'MRVL',
        'target_price': None,
        'note': (
            'Custom silicon / data center / AI infrastructure. Similar regime profile to NVDA — '
            'not a Quadrant D fit (high multiple, growth, no FCF cushion). Hold on watchlist for '
            'a regime shift toward B (Fed BS > $7T + cut prob > 30%) or for a major valuation reset.'
        ),
    },
    # === Quadrant D regime-fit additions (added 2026-06-03) ===
    'WPM': {
        'ticker': 'WPM',
        'target_price': None,
        'note': (
            'Wheaton Precious Metals — gold/silver streaming. Asset-light leverage to GLDM thesis '
            'with real FCF (vs miners with capex risk). Quadrant D fit: real assets + pricing power. '
            'Entry: confirm 5Y avg P/E vs current; size as Tier-1 satellite candidate if GLDM grows.'
        ),
    },
    'MOS': {
        'ticker': 'MOS',
        'target_price': None,
        'note': (
            'Mosaic — phosphate/potash fertilizer. Complements NTR food-security thesis; pure-play '
            'commodity exposure. Quadrant D fit: real asset, inflation-linked. '
            'Entry: only if NTR thesis confirms and Mosaic trades at <12x forward earnings.'
        ),
    },
    'LIN': {
        'ticker': 'LIN',
        'target_price': None,
        'note': (
            'Linde — industrial gases duopoly (with APD on QB list). Defensive compounder with '
            'pricing power and contractual revenue. Quadrant D fit: pricing power + FCF moat. '
            'Entry: research P/E vs 5Y avg first; rich quality names often start above fair value.'
        ),
    },
    # Quadrant B rotation candidates — DO NOT enter yet. Monitor for Fed BS > $7T + cut prob > 30%.
    'QB_ISRG':  {'ticker': 'ISRG',  'action': 'WATCH', 'note': 'Quadrant B candidate — surgical robotics growth'},
    'QB_APD':   {'ticker': 'APD',   'action': 'WATCH', 'note': 'Quadrant B candidate — industrial gases / green hydrogen'},
    'QB_FCX':   {'ticker': 'FCX',   'action': 'WATCH', 'note': 'Quadrant B candidate — copper / critical minerals'},
    'QB_CCJ':   {'ticker': 'CCJ',   'action': 'WATCH', 'note': 'Quadrant B candidate — uranium / nuclear renaissance'},
}