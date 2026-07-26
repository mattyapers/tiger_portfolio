"""
settings_satellite.py — Single source of truth for the Satellite/risk book.

Credentials (TIGER_ID, ACCOUNT, PRIVATE_KEY_PATH, LICENSE) are loaded from .env
via python-dotenv — same account as config/settings.py, this is the same repo.

SPLIT 2026-07-24: Core + Core-Plus (long-term, passive buy-and-hold money)
live in config/settings.py. This module owns every active, thesis-driven,
higher-conviction position — tracked as its own 100% pie, not as a 21%
slice of a blended one. Run it with `python main.py --satellite`. Both
books share every module in modules/ and point at the same Tiger account;
each one only classifies its own slice of tickers (see TICKER_TIERS below),
and modules/transform.py's classify_tiers() drops anything not in
TICKER_TIERS before computing totals — that's what stops the two books'
positions from bleeding into each other's weight/drift math
("double-dipping into risk").
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# TIGER BROKERS API CONFIG (loaded from .env)
# ============================================================
# Same brokerage account as config/settings.py — this book just reports on
# a different subset of the same account's positions.
TIGER_ID = os.getenv('TIGER_ID', '')
ACCOUNT = os.getenv('TIGER_ACCOUNT', '')
PRIVATE_KEY_PATH = os.getenv('TIGER_PRIVATE_KEY_PATH', 'config/tiger_private_key.pem')
LICENSE = os.getenv('TIGER_LICENSE', 'TBSG')

# ============================================================
# PORTFOLIO STRUCTURE — single tier, 100% of THIS book
# ============================================================
# There is only one tier here on purpose: this whole book IS the
# satellite/risk sleeve now, not a 21% piece of something bigger.
TIER_TARGETS = {
    'Satellite': 1.00,
}

# Every ticker this book owns. Add a new one here (and to
# SATELLITE_TARGETS + PE_5Y_AVERAGES) when initiating a new position.
TICKER_TIERS = {
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
    # 'MSFT': 'Satellite',  # WATCHLIST — uncomment when entry conditions met (see WATCHLIST['MSFT_WATCH'])
}

# ============================================================
# TIER DEFINITIONS — Conviction-weighted positioning within this book
# ============================================================
# Tier-1 (12-15%): Highest conviction, regime-aligned, multi-year hold
#   → GLDM (inflation hedge), RTX (defense), GOOG (AI/Cloud compounder)
# Standard (7%): Thesis-driven, full allocation
#   → NVDA, TSM, AAPL, MA, CAT, AON
# Reduced (4-5%): Held with lower conviction or partial thesis conflict
#   → KO (dividend only, no growth edge), BABA (deglobalization conflict)
# ============================================================
SATELLITE_TARGETS = {
    'GLDM': 0.15,   # Tier-1 — Defensive hedge, stagflation + geopolitical
    'RTX':  0.15,   # Tier-1 — Defense theme, NATO spending catalyst
    'GOOG': 0.12,   # Tier-1 — AI + Cloud growth compounder
    'NVDA': 0.07,   # Standard — AI infrastructure
    'TSM':  0.07,   # Standard — Semiconductor / deglobalization thesis
    'AAPL': 0.07,   # Standard — Consumer tech
    'MA':   0.07,   # Standard — Payments / cashless economy
    'CAT':  0.05,   # Reduced — P/E elevated; hold but cap until reversion
    'AON':  0.07,   # Standard — Risk management / insurance
    'KO':   0.03,   # Reduced — Defensive dividend, trim to make room
    'BABA': 0.01,   # Minimum — Deglobalization conflict, hold/exit candidate
    'XLE':  0.07,   # Standard — Energy hedge, stagflation alpha
    'COP':  0.04,   # Small — ConocoPhillips opportunistic, stagflation energy
    'NTR':  0.03,   # Small — Nutrien potash, food security / commodity
}
_target_sum = sum(SATELLITE_TARGETS.values())
assert abs(_target_sum - 1.00) < 0.01, \
    f"SATELLITE_TARGETS sum {_target_sum:.2f} != 1.00 — check tier allocations"

# ============================================================
# REBALANCING RULES
# ============================================================
# max_position_pct now caps a position's share of this ENTIRE book
# (not a sub-sleeve within a blended whole) — same 15% number as before,
# but it means something bigger now that this book is 100% of its own pie.
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
SIGNAL_RULES = {
    'pe_max': 30,
    'pe_premium_trim': 0.25,
    'stop_loss_pct': -0.15,
    'take_profit_pct': 1.00,
}

# ============================================================
# 5-YEAR AVERAGE P/E RATIOS (updated 2026-07-24)
# ============================================================
PE_5Y_AVERAGES = {
    'GOOG': 25.0,
    'RTX':  33.0,
    'NVDA': 65.0,
    'TSM':  23.0,
    'AAPL': 30.0,
    'MA':   36.0,
    'CAT':  20.0,
    'KO':   25.5,
    'BABA': 15.0,   # Unresolved — no clean 5Y avg found in last refresh, kept prior value
    'AON':  25.0,   # Unresolved — no clean 5Y avg found in last refresh, kept prior value
    'COP':  14.0,   # Energy cyclical — 5Y avg depressed by 2020 crash
    'NTR':  34.0,
}

# ============================================================
# MACRO REGIME — Updated 2026-07-24
# ============================================================
# Same regime call as config/settings.py (both books reviewed on the same
# 14-day cycle by the same person) — the satellite_overrides in
# REGIME_PLAYBOOK below are what actually differ, since only this book
# has satellite positions to tilt.
MACRO_REGIME = {
    'as_of_date': '2026-07-24',
    'quadrant': 'D',
    'regime_label': 'Stagflation / Hike-Risk Escalating — Hormuz Effectively Closed, Oil Shock Underway',
    'confidence': 'high',
    'fed_funds_rate': '3.50–3.75% (held since Dec 2025 cut); July 28-29 FOMC: 63.5% hold / ~35-36.5% hike probability (Jul 23 print) — hike risk resurfacing, down from 73.4% hold two weeks prior',
    'fed_balance_sheet': '$6.736T total assets (H.4.1, wk of Jul 9); $264B below $7T QB trigger; roughly flat (+$7B wk, +$83B YoY)',
    'pce_headline': 'June print due Jul 30, 2026 (not yet released); Truflation nowcast ~3.7% YoY, cooling slightly from May 4.07%',
    'pce_core': 'June print due Jul 30, 2026 (not yet released); Truflation nowcast +0.2% MoM / ~3.3% YoY — still elevated',
    'cpi_latest': '3.5% YoY headline (June print, released Jul 14); prior May print 4.2%/2.9% core',
    'jobs_may': "June payrolls +57k (vs 115k consensus), well below May's downwardly-revised +129k; unemployment 4.2% (participation fell to 61.5%, lowest since Mar 2021) — soft print despite hot inflation",
    'yield_curve': '10Y 4.55% / 2Y 4.18% (Jul 17 close) ≈ +34-37bp; positive, stable range all month',
    'vix': '18.70, +12.4% (Jul 23 close) — rising, still below 25 breach but repricing fast on Hormuz closure',
    'brent': '$97-100/bbl (Jul 23-24) — breached $100 intraday Fri for first time in 2 months on Hormuz closure + new Red Sea/Houthi front',
    'fedwatch_next_meeting': 'July 28-29 FOMC: 63.5% hold / ~35-36.5% hike probability (Jul 23) — down from 73.4% hold reading two weeks ago',
    'fedwatch_dec_cumulative': '~78.2% no-change / ~15.4% cut / ~5.4% hike cumulative to Dec 2026 (unchanged reading)',
    'hormuz_status': 'EFFECTIVELY CLOSED (Jul 23) — only 15 ships transited Jul 19 vs ~88/day normal; Iran PGSA declared passage "not possible" Jul 12; IRGC struck Cyprus-flagged container ship Jul 11 (23 crew stranded, 1 missing). Major escalation from "contested/reopening" two weeks ago.',
    'tariff_section_122': 'Statutory Section 122 duties expire today (Jul 24, 2026); Federal Circuit appeal (CAFC stay since Jun 11) still unresolved, government brief due in July — litigation outcome pending regardless of statutory lapse',
    'mas_stance': 'No Jul 2026 quarterly statement located yet (MAS issues Jan/Apr/Jul/Oct); last confirmed reading Jan 29, 2026 held steady, raised 2026 inflation outlook to 1-2%. Apr 14 slope-steepening note from prior cycle is stale — verify mas.gov.sg directly.',
    'open_inflections': [
        'Hormuz closure escalation (Jul 11-23) — major regime-confirming shock; watch for de-escalation or a wider Red Sea front',
        'Fed hike risk resurfacing — 35%+ probability for Jul 29 FOMC, up from near-zero; first live hike discussion since cuts began',
        'Section 122 tariff statutory expiry today (Jul 24) vs ongoing CAFC appeal — outcome unresolved, watch for new proclamation or lapse',
        'June PCE report due Jul 30 — will confirm/deny Truflation nowcast (3.7% headline / 3.3% core)',
        'MAS Jul quarterly statement overdue/unlocated — verify directly, could shift SGD policy read',
        'Fed BS vs $7T + Dec cut prob vs 30% — Quadrant B rotation trigger, still far ($264B / ~15pp away)',
    ],
    'quadrant_b_distance': 'far',
}

# ============================================================
# REGIME PLAYBOOK — drives satellite tilts (no bond sleeve here)
# ============================================================
REGIME_PLAYBOOK = {
    'Stagflation': {
        'satellite_overrides': {'GLDM': 0.22, 'RTX': 0.18, 'KO': 0.10, 'NVDA': 0.05},
    },
    'Growth/LowInflation': {
        'satellite_overrides': {},
    },
    'Recession/Deflation': {
        'satellite_overrides': {'GLDM': 0.15},
    },
    'Risk-Off/Transition': {
        'satellite_overrides': {'GLDM': 0.20},
    },
}

# ============================================================
# MONTHLY CONTRIBUTIONS (SGD → USD at 0.79)
# ============================================================
# core_sgd lives in config/settings.py now.
MONTHLY_CONTRIB = {
    'satellite_sgd': 300,
    'fx_rate': 0.79,
}

# ============================================================
# OUTPUT CONFIG — separate files from config/settings.py so running both
# books never overwrites the other's Excel/snapshot/dashboard/log.
# ============================================================
OUTPUT_PATH = 'output/satellite_tracker.xlsx'
NAS_PATH = '/volume1/investments/satellite_portfolio_tracker.xlsx'
SNAPSHOT_PATH = 'output/satellite_snapshot.json'
DASHBOARD_PATH = 'output/satellite_dashboard.html'

# ============================================================
# SNAPSHOT DATE
# ============================================================
SNAPSHOT_DATE = '2026-07-24'

# ============================================================
# DATA FRESHNESS METADATA
# ============================================================
DATA_FRESHNESS = {
    'snapshot_date': {
        'value':         SNAPSHOT_DATE,
        'cadence_days':  14,
        'label':         'Holdings snapshot',
        'update_action': 'Run main.py --satellite (any extract mode); bump SNAPSHOT_DATE to today',
    },
    'macro_regime': {
        'value':         '2026-07-24',
        'cadence_days':  7,
        'label':         'Macro regime block',
        'update_action': 'Update MACRO_REGIME dict + open_inflections in settings_satellite.py; bump value here',
    },
    'pe_5y_averages': {
        'value':         '2026-07-24',
        'cadence_days':  90,
        'label':         '5Y P/E averages (quarterly)',
        'update_action': 'Refresh PE_5Y_AVERAGES from Macrotrends/YF; bump value here',
    },
    'satellite_targets': {
        'value':         '2026-07-24',
        'cadence_days':  30,
        'label':         'Satellite tier weights',
        'update_action': 'Review SATELLITE_TARGETS for post-trade changes; bump value here',
    },
    'watchlist': {
        'value':         '2026-07-24',
        'cadence_days':  14,
        'label':         'Watchlist pending actions',
        'update_action': 'Resolve or extend each WATCHLIST entry; bump value here',
    },
    'offline_prices': {
        'value':         SNAPSHOT_DATE,
        'cadence_days':  14,
        'label':         'extract_offline() prices',
        'update_action': 'Run main.py --satellite --yf-only or --satellite; SNAPSHOT_DATE auto-syncs',
    },
}

# ============================================================
# WATCHLIST — moved wholesale from config/settings.py (2026-07-24 split).
# Every entry here was already about a satellite/active-thesis ticker.
# ============================================================
WATCHLIST = {
    'BABA_EXIT': {
        'ticker': 'BABA',
        'action': 'EXIT',
        'note': (
            'STOP-LOSS TRIGGERED 2026-04-18: -15.8% loss ($138.59 vs $164.69 cost). '
            'Override log (2026-03-31): "No further overrides on BABA. '
            'Next breach of -15% from current price = execute exit, no exceptions." '
            '2026-07-24 run: BABA not flagged in that cycle\'s Trim/Entry Signals — check current P&L% on Entry Signals sheet; '
            'if still below -15% cost basis, override log says execute now, no exceptions. '
            'Sell 1 share (~$138 proceeds). Redeploy into GLDM (underweight) or AON (score 1 entry). '
            'After execution: remove BABA from TICKER_TIERS and SATELLITE_TARGETS.'
        ),
        'trigger_date': '2026-04-18',
    },
    'XLE_DEFERRED': {
        'ticker': 'XLE',
        'action': 'ENTRY CONDITION MET',
        'note': (
            'Original thesis: stagflation + oil >$100 = energy alpha. Oil dropped to $88 on Iran ceasefire (Apr 8), thesis weakened, deferred. '
            'TRIGGER HIT 2026-07-24: Hormuz effectively closed (Jul 11-23, only 15 ships transited Jul 19 vs ~88/day normal) + new Houthi Red Sea front. '
            'Brent breached $100 intraday Jul 23-24, first time in 2 months. Entry condition (oil >$95 post-ceasefire-collapse) satisfied. '
            'Verify current XLE price/P/E via Screener sheet before sizing; XLE at 0.07 target with no position — resume normal ADD tranches.'
        ),
        'review_date': '2026-07-24',
    },
    'CAT_TRIM': {
        'ticker': 'CAT',
        'action': 'TRIM 50%',
        'note': (
            'P/E ~48x (Jul 2026) vs revised 5Y avg 20.0 (was 19.0) — still ~140% premium. Score 5 — both trim triggers firing, still active this cycle. '
            'Override on 2026-03-31 was correct (+$80/share gain). '
            'Recommend trimming 50% at current levels. Check Entry Signals sheet for live price/P/E. '
            'Proceeds → AON or MA. Re-entry target: $580.'
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
            'Catalyst date (2026-04-29 Q3 earnings) has passed — NOT YET RESOLVED, needs manual research this cycle. '
            'Entry requires: Azure Q3 growth >= 38%, '
            'CapEx guidance plateaus, stock holds above $380 post-earnings, '
            'no adverse OpenAI lawsuit outcome. Target 5-7% of this book if met. '
            'Also unresolved given current regime: MSFT scored regime-misfit (❌) for Quadrant D in WATCHLIST_REGIME_FIT — '
            'confirm whether stagflation/hike-risk thesis still argues against entry regardless of earnings outcome.'
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
        'ticker': 'D05.SI',   # bare 'DBS' resolves to Invesco DB Silver Fund on Yahoo/yfinance, wrong instrument
        'target_price': None,
        'note': 'Singapore bank — SGD base, ASEAN growth. Price quoted in SGD (SGX-listed), not USD like the rest of the watchlist.',
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
            'a regime shift toward B (Fed BS > $7T + cut prob > 30%) or for a major valuation reset. '
            'NOTE: 1 share of MRVL is already held in the Tiger account (cost $300.345) but is not in '
            'TICKER_TIERS here or in config/settings.py — it is currently invisible to both books\' '
            'totals post-split. Either add it to TICKER_TIERS/SATELLITE_TARGETS here, or track it manually.'
        ),
    },
    'WPM': {
        'ticker': 'WPM',
        'target_price': None,
        'note': (
            'Wheaton Precious Metals — gold/silver streaming. Asset-light leverage to GLDM thesis '
            'with real FCF (vs miners with capex risk). Quadrant D fit: real assets + pricing power. '
            'Entry: confirm 5Y avg P/E vs current; size as Tier-1 candidate if GLDM grows.'
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

# ============================================================
# WATCHLIST REGIME FIT — Quadrant D scoring for screener
# ============================================================
# score: ✅ = regime-fit (hard asset, defense, pricing power, short duration)
#        ⚠️ = neutral (thesis intact but not regime-optimal)
#        ❌ = regime-misfit (high multiple, no FCF, long duration, China-dependent)
WATCHLIST_REGIME_FIT = {
    'BABA': {'score': '❌', 'reason': 'China-dependent; deglobalization conflict'},
    'XLE':  {'score': '✅', 'reason': 'Energy hedge; stagflation alpha'},
    'CAT':  {'score': '⚠️', 'reason': 'Industrial compounder; P/E elevated vs 5Y avg'},
    'MSFT': {'score': '❌', 'reason': 'High multiple; long-duration growth proxy; QB fit not D'},
    'LMT':  {'score': '✅', 'reason': 'Defense; NATO spending catalyst; FCF compounder'},
    'EUAD': {'score': '✅', 'reason': 'European defense ETF; NATO rearmament theme'},
    'D05.SI': {'score': '⚠️', 'reason': 'SGD base + ASEAN growth; rate-sensitive NIM compression risk'},
    'COPX': {'score': '⚠️', 'reason': 'Copper miners; real assets but cyclical in stagflation'},
    'MRVL': {'score': '❌', 'reason': 'High multiple; no FCF cushion; hold for QB or valuation reset'},
    'WPM':  {'score': '✅', 'reason': 'Gold/silver streaming; real assets + FCF (no capex risk)'},
    'MOS':  {'score': '✅', 'reason': 'Fertilizer/potash; food security; inflation-linked commodity'},
    'LIN':  {'score': '✅', 'reason': 'Pricing power + contractual FCF; industrial gases duopoly'},
    'ISRG': {'score': '❌', 'reason': 'High multiple; growth; no FCF cushion; QB candidate not D'},
    'APD':  {'score': '⚠️', 'reason': 'QB candidate; industrial gases; neutral in D pending BS trigger'},
    'FCX':  {'score': '⚠️', 'reason': 'Copper/critical minerals; real assets but cyclical in stagflation'},
    'CCJ':  {'score': '⚠️', 'reason': 'Uranium/nuclear; QB candidate; real-asset case in D is weak'},
}
