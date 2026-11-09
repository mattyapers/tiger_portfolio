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
    'AON':  'Satellite',
    'XLE':  'Satellite',
    'COP':  'Satellite',   # ConocoPhillips — energy/stagflation thesis
    'NTR':  'Satellite',   # Nutrien — potash/commodity/food security
    # 'MSFT': 'Satellite',  # Closed 2026-07-28 (regime-misfit, see WATCHLIST_REGIME_FIT['MSFT']) — reopen only on a genuine Quadrant B shift
}

# ============================================================
# TIER DEFINITIONS — Conviction-weighted positioning within this book
# ============================================================
# Tier-1 (12-15%): Highest conviction, regime-aligned, multi-year hold
#   → GLDM (inflation hedge), RTX (defense), GOOG (AI/Cloud compounder)
# Standard (7%): Thesis-driven, full allocation
#   → NVDA, TSM, AAPL, MA, CAT, AON
# Reduced (4-5%): Held with lower conviction or partial thesis conflict
#   → KO (dividend only, no growth edge)
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
    'XLE':  0.08,   # Standard — Energy hedge, stagflation alpha; +1% absorbed from BABA exit (2026-07-28) — best-conviction unfunded name at the time
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
NAV_HISTORY_PATH = 'output/nav_history_satellite.json'

# ============================================================
# SNAPSHOT DATE
# ============================================================
SNAPSHOT_DATE = '2026-11-09'

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
        'value':         '2026-11-09',
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
        'value':         '2026-08-29',
        'cadence_days':  30,
        'label':         'Satellite tier weights',
        'update_action': 'Review SATELLITE_TARGETS for post-trade changes; bump value here',
    },
    'watchlist': {
        'value':         '2026-10-27',
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
    # BABA_EXIT resolved 2026-07-28 — confirmed 0 BABA shares in the live snapshot,
    # stop-loss exit already executed. Removed from TICKER_TIERS/SATELLITE_TARGETS/
    # PE_5Y_AVERAGES per this entry's own closeout instructions; freed 1% target
    # weight absorbed into XLE (best-conviction unfunded name at the time).
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
    # MSFT_WATCH CLOSED 2026-07-28 — catalyst date (Apr 29) sat unresolved 90 days,
    # past the 2-cycle (28-day) forcing threshold in stage2_weekly_review.md's
    # Watchlist Review. Regime argument (❌ regime-misfit, Quadrant D still
    # confirmed and if anything more hike-risk-elevated this cycle) settles it
    # independent of the earnings condition — forced verdict: CLOSE.
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
    # GRMN CLOSED 2026-08-29 — review_date (Jul 28) sat unresolved 32 days,
    # past the 2-cycle (28-day) forcing threshold in stage2_weekly_review.md's
    # Watchlist Review. Screener confirms regime-fit ⚠️ (quality compounder, not
    # a stagflation/Quadrant D hedge) and no pullback ever materialized —
    # forced verdict: CLOSE, don't keep chasing a weak regime match.
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
    'XLE':  {'score': '✅', 'reason': 'Energy hedge; stagflation alpha'},
    'CAT':  {'score': '⚠️', 'reason': 'Industrial compounder; P/E elevated vs 5Y avg'},
    'MSFT': {'score': '❌', 'reason': 'High multiple; long-duration growth proxy; QB fit not D'},
    'GRMN': {'score': '⚠️', 'reason': 'Quality consumer-tech compounder, real revenue growth + FCF, but not a stagflation hedge — no pricing-power/hard-asset/defense angle for Quadrant D specifically'},
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
