"""
transform.py — Stage 2: Calculate portfolio metrics and generate signals.

THIS IS THE BRAIN OF THE SYSTEM.

LOGIC FLOW:
1. Classify positions into tiers (Core / Core-Plus / Satellite)
2. Calculate weights (portfolio-level and within-satellite)
3. Compute drift from targets → generates rebalance signals
4. Score entry/exit opportunities using valuation rules
5. Run correlation analysis on satellite positions

DESIGN PRINCIPLE:
Every function takes a DataFrame in, returns a DataFrame out.
This makes each step testable independently (good for learning SQL/Python patterns).
"""

import pandas as pd
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def classify_tiers(positions_df, settings):
    """
    Add tier classification to each position.

    WHY: Your 68/11/21 allocation requires knowing which tier each position
    belongs to. This drives all downstream weight calculations.

    SQL EQUIVALENT:
    SELECT *, CASE
        WHEN symbol IN ('VOO','VXUS',...) THEN 'Core'
        WHEN symbol IN ('SPYD','ONEQ') THEN 'Core-Plus'
        ELSE 'Satellite'
    END AS tier
    FROM positions
    """
    df = positions_df.copy()
    df['tier'] = df['symbol'].map(settings.TICKER_TIERS).fillna('Unknown')

    tier_counts = df.groupby('tier').size().to_dict()
    logger.info(f"Tier classification: {tier_counts}")
    return df


def calculate_weights(df, account_summary):
    """
    Calculate portfolio weights at two levels:
    1. Weight % of total portfolio (for tier-level tracking)
    2. Weight % within satellite (for position-level rebalancing)

    WHY TWO LEVELS:
    - Tier weight tells you if Core/Satellite balance is drifting
    - Satellite weight tells you if any single pick is too large

    SQL EQUIVALENT:
    SELECT *,
        market_value / SUM(market_value) OVER() AS wt_portfolio,
        CASE WHEN tier = 'Satellite'
            THEN market_value / SUM(market_value) OVER(WHERE tier='Satellite')
        END AS wt_satellite
    FROM classified_positions
    """
    total_value = df['market_value'].sum()
    satellite_value = df.loc[df['tier'] == 'Satellite', 'market_value'].sum()

    df['wt_portfolio'] = df['market_value'] / total_value if total_value > 0 else 0
    df['wt_satellite'] = np.where(
        df['tier'] == 'Satellite',
        df['market_value'] / satellite_value if satellite_value > 0 else 0,
        np.nan
    )

    # P&L percentage
    df['pnl_pct'] = np.where(
        df['cost_basis'] > 0,
        df['unrealized_pnl'] / df['cost_basis'],
        0
    )

    logger.info(f"Total portfolio: ${total_value:,.2f} | Satellite: ${satellite_value:,.2f}")
    # Core-Bond counts toward the Core 68% target
    core_equity = df.loc[df['tier'] == 'Core', 'market_value'].sum()
    core_bond = df.loc[df['tier'] == 'Core-Bond', 'market_value'].sum()
    return df, {
        'total_value': total_value,
        'satellite_value': satellite_value,
        'core_value': core_equity + core_bond,
        'core_equity_value': core_equity,
        'core_bond_value': core_bond,
        'coreplus_value': df.loc[df['tier'] == 'Core-Plus', 'market_value'].sum(),
    }


def calculate_tier_drift(portfolio_totals, settings):
    """
    Calculate how far each tier has drifted from target allocation.

    RETURNS list of dicts with tier health status.

    WHY: If Satellite grows to 30% (target 21%), you're overexposed
    to active risk. This catches drift before it compounds.
    """
    total = portfolio_totals['total_value']
    if total == 0:
        return []

    results = []
    for tier, target in settings.TIER_TARGETS.items():
        key = tier.lower().replace('-', '') + '_value'
        # Map tier names to keys
        value_map = {
            'Core': portfolio_totals['core_value'],
            'Core-Plus': portfolio_totals['coreplus_value'],
            'Satellite': portfolio_totals['satellite_value'],
        }
        actual_value = value_map.get(tier, 0)
        actual_pct = actual_value / total
        drift = actual_pct - target

        if abs(drift) > 0.05:
            status = '🚨 Rebalance'
        elif abs(drift) > 0.03:
            status = '⚠️ Drifting'
        else:
            status = '✅ On Target'

        results.append({
            'tier': tier,
            'target_pct': target,
            'actual_pct': actual_pct,
            'actual_value': actual_value,
            'drift': drift,
            'status': status,
        })

    return results


def generate_rebalance_signals(df, settings):
    """
    Generate actionable rebalance signals for satellite positions.

    LOGIC (your rules encoded):
    1. If position > max_position_pct (10%) → 🚨 BREACH, trim immediately
    2. If drift > drift_threshold (3%)     → ⚠️ TRIM to target
    3. If drift < -drift_threshold (-3%)   → 💡 ADD if cash available
    4. Otherwise                           → ✅ HOLD

    RETURNS DataFrame with signal, action, shares_to_trade, est_proceeds

    SQL EQUIVALENT:
    SELECT *,
        CASE
            WHEN wt_satellite > 0.10 THEN '🚨 BREACH MAX'
            WHEN wt_satellite - target > 0.03 THEN '⚠️ TRIM'
            WHEN target - wt_satellite > 0.03 THEN '💡 ADD'
            ELSE '✅ HOLD'
        END AS signal
    FROM satellite_positions
    """
    rules = settings.REBALANCE_RULES
    sat = df[df['tier'] == 'Satellite'].copy()

    if sat.empty:
        return pd.DataFrame()

    sat_total = sat['market_value'].sum()

    # Map targets
    sat['target_pct'] = sat['symbol'].map(settings.SATELLITE_TARGETS).fillna(0.07)
    sat['target_value'] = sat_total * sat['target_pct']
    sat['drift_dollars'] = sat['market_value'] - sat['target_value']
    sat['drift_pct'] = sat['wt_satellite'] - sat['target_pct']

    # Signal logic
    # Effective cap = max(target, hard_cap). So RTX at 18% target
    # won't breach at 10% — only if it exceeds its own 18% target.
    effective_cap = sat['target_pct'].clip(lower=rules['max_position_pct'])

    conditions = [
        sat['wt_satellite'] > effective_cap,
        sat['drift_pct'] > rules['drift_threshold'],
        sat['drift_pct'] < -rules['drift_threshold'],
    ]
    choices = ['🚨 BREACH MAX', '⚠️ TRIM', '💡 ADD']
    sat['signal'] = np.select(conditions, choices, default='✅ HOLD')

    # Action text
    sat['action'] = sat.apply(lambda r: _action_text(r, rules), axis=1)

    # Shares to trade (positive = sell, negative = buy)
    sat['shares_to_trade'] = np.where(
        abs(sat['drift_pct']) > rules['drift_threshold'],
        sat['drift_dollars'] / sat['latest_price'],
        0
    )
    sat['est_proceeds'] = np.where(
        abs(sat['drift_pct']) > rules['drift_threshold'],
        sat['drift_dollars'],
        0
    )

    return sat


def _action_text(row, rules):
    """Generate human-readable action for each position."""
    effective_cap = max(row['target_pct'], rules['max_position_pct'])
    if row['wt_satellite'] > effective_cap:
        return f"TRIM to {effective_cap:.0%} immediately"
    if row['drift_pct'] > rules['drift_threshold']:
        return f"Trim ${abs(row['drift_dollars']):.0f} to target"
    if row['drift_pct'] < -rules['drift_threshold']:
        return f"Consider adding ${abs(row['drift_dollars']):.0f}"
    return "No action needed"


def score_entry_exit(df, settings):
    """
    Score each satellite position for entry/exit timing.

    YOUR RULES (from CAT thesis):
    - TRIM trigger: P/E > 30 AND > 25% above 5Y average
    - STOP LOSS: P&L < -15%
    - ENTRY: P/E below 5Y average = good value

    SCORING (1-5, lower = better entry):
    5 = PE > 30 AND premium > 25% (worst — trim candidate)
    4 = PE > 30 OR premium > 25%
    3 = Slightly above average
    2 = Near historical average
    1 = Below average (best entry)

    WHY A SCORE: Reduces emotion. A number is harder to argue with
    than a feeling about whether a stock is "expensive."
    """
    sat = df[df['tier'] == 'Satellite'].copy()
    rules = settings.SIGNAL_RULES

    # Map 5Y P/E averages
    sat['pe_5y_avg'] = sat['symbol'].map(settings.PE_5Y_AVERAGES)

    # PE premium vs 5Y average
    sat['pe_premium'] = np.where(
        sat['pe_5y_avg'].notna() & (sat['pe_5y_avg'] > 0),
        (sat['pe_ttm'] - sat['pe_5y_avg']) / sat['pe_5y_avg'],
        np.nan
    )

    # Cost distance (how far price is from your entry)
    sat['cost_distance'] = np.where(
        sat['avg_cost'] > 0,
        (sat['latest_price'] - sat['avg_cost']) / sat['avg_cost'],
        0
    )

    # Entry score
    def _score(row):
        pe = row.get('pe_ttm')
        prem = row.get('pe_premium')
        if pd.isna(pe) or pd.isna(prem):
            return np.nan
        if pe > rules['pe_max'] and prem > rules['pe_premium_trim']:
            return 5
        if pe > rules['pe_max'] or prem > rules['pe_premium_trim']:
            return 4
        if prem > 0:
            return 3
        if prem > -0.15:
            return 2
        return 1

    sat['entry_score'] = sat.apply(_score, axis=1)

    # Signal text
    def _signal(row):
        if pd.notna(row['pe_ttm']):
            if row['pe_ttm'] > rules['pe_max'] and row.get('pe_premium', 0) > rules['pe_premium_trim']:
                return '🚨 TRIM — PE+Premium trigger'
            if row['pe_ttm'] > rules['pe_max']:
                return '⚠️ WATCH — PE elevated'
        if row['pnl_pct'] < rules['stop_loss_pct']:
            return '🛑 STOP LOSS — Exit'
        if row.get('entry_score') and row['entry_score'] <= 2:
            return '💡 ENTRY — Good value'
        return '✅ HOLD'

    sat['entry_signal'] = sat.apply(_signal, axis=1)

    return sat


def build_portfolio_summary(df, portfolio_totals, tier_drift, account_summary):
    """
    Build a summary dict for the dashboard.

    RETURNS dict with all key metrics for Excel dashboard output.
    """
    sat = df[df['tier'] == 'Satellite']
    return {
        'total_portfolio': portfolio_totals['total_value'],
        'core_value': portfolio_totals['core_value'],
        'coreplus_value': portfolio_totals['coreplus_value'],
        'satellite_value': portfolio_totals['satellite_value'],
        'core_pct': portfolio_totals['core_value'] / portfolio_totals['total_value'] if portfolio_totals['total_value'] > 0 else 0,
        'coreplus_pct': portfolio_totals['coreplus_value'] / portfolio_totals['total_value'] if portfolio_totals['total_value'] > 0 else 0,
        'satellite_pct': portfolio_totals['satellite_value'] / portfolio_totals['total_value'] if portfolio_totals['total_value'] > 0 else 0,
        'total_pnl': df['unrealized_pnl'].sum(),
        'total_pnl_pct': df['unrealized_pnl'].sum() / df['cost_basis'].sum() if df['cost_basis'].sum() > 0 else 0,
        'cash_balance': account_summary.get('cash_balance', 0),
        'positions_count': len(df),
        'satellite_count': len(sat),
        'timestamp': datetime.now().isoformat(),
        'tier_drift': tier_drift,
    }


def transform_all(raw_data, settings):
    """
    Master transform function — runs the full analytics pipeline.

    INPUT: raw_data dict from extract stage
    OUTPUT: dict with all calculated metrics ready for Excel export
    """
    df = raw_data['positions'].copy()

    # Merge live prices if available
    quotes = raw_data.get('quotes')
    if quotes is not None and not quotes.empty and 'latest_price' in quotes.columns:
        price_map = quotes.set_index('symbol')['latest_price'].to_dict()
        df['latest_price'] = df['symbol'].map(price_map).fillna(df.get('latest_price', 0))
        df['market_value'] = df['shares'] * df['latest_price']
        df['unrealized_pnl'] = df['market_value'] - df['cost_basis']

        if 'pe_ttm' in quotes.columns:
            pe_map = quotes.set_index('symbol')['pe_ttm'].to_dict()
            df['pe_ttm'] = df['symbol'].map(pe_map)

    # Step 1: Classify
    df = classify_tiers(df, settings)

    # Step 2: Weights
    df, portfolio_totals = calculate_weights(df, raw_data['account'])

    # Step 3: Tier drift
    tier_drift = calculate_tier_drift(portfolio_totals, settings)

    # Step 4: Rebalance signals
    rebalance_df = generate_rebalance_signals(df, settings)

    # Step 5: Entry/exit signals
    entry_df = score_entry_exit(df, settings)

    # Step 6: Summary
    summary = build_portfolio_summary(df, portfolio_totals, tier_drift, raw_data['account'])

    return {
        'holdings': df,
        'rebalance': rebalance_df,
        'entry_signals': entry_df,
        'summary': summary,
        'tier_drift': tier_drift,
        'timestamp': raw_data['timestamp'],
    }