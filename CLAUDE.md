# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Tiger Portfolio Tracker is a Python ETL pipeline for automated investment portfolio management. It connects to the Tiger Brokers API (Singapore brokerage) for live positions, pulls prices via yfinance, calculates allocation drift and macro-regime-based signals, and writes a dynamic Excel report.

## Running the Pipeline

```bash
# Hybrid (default) — Tiger positions + yfinance prices
python main.py

# YF-Only — offline shares + live yfinance prices (no Tiger API needed)
python main.py --yf-only

# Offline — uses latest auto-saved snapshot (no internet)
python main.py --offline
```

Output: `output/portfolio_tracker.xlsx` and `output/run_YYYYMMDD_HHMM.log`.

## Dependencies

```bash
pip install tigeropen yfinance openpyxl pandas numpy
```

Credentials required in `config/`:
- `tiger_private_key.pem` — RSA private key for Tiger API auth

## Architecture

Three independent, sequentially-executed stages, each in its own module:

**Stage 1 — `modules/extract.py`**
Three extract modes based on CLI flag:
- `extract_hybrid()` — authenticates with Tiger (RSA-signed), fetches positions, then overlays live prices + P/E from yfinance. Auto-detects and fixes fractional share inflation (Tiger sometimes reports 0.6849 as 6849; fix: `real_shares = tiger_market_value / yf_price`). Saves result to `output/latest_snapshot.json`.
- `extract_yf_only()` — uses hardcoded/snapshot shares, fetches live prices from yfinance. Also saves snapshot.
- `extract_offline()` — loads `output/latest_snapshot.json` if it exists; falls back to hardcoded data in `_extract_hardcoded()`.

**Stage 2 — `modules/transform.py`**
Pure data transformation — no I/O. Takes the extracted DataFrames and produces:
- Tier classification (Core / Core-Bond / Core-Plus / Satellite) per ticker
- Portfolio weights and drift vs. targets
- Rebalance signals (TRIM / ADD / HOLD) using the 3% drift threshold
- Macro-regime-based bond sleeve and satellite signals
- P/E-based entry/exit scores (1–5 scale)
- Satellite correlation matrix

**Stage 3 — `modules/load.py`**
Writes to Excel using `openpyxl`. Generates four sheets: Dashboard, Holdings, Rebalance Signals, Entry Signals. Blue cells = editable inputs; black = Excel formulas; yellow = attention flags.

**Orchestrator — `main.py`**
Calls the three stages in sequence. Handles logging setup. Selects extract mode from CLI args.

## Configuration

All tunable parameters live in `config/settings.py` — no values are hardcoded in the modules:

- **Tiger API credentials** — `TIGER_ID`, `ACCOUNT`, `PRIVATE_KEY_PATH`, `LICENSE`
- **Portfolio structure** — `TIER_TARGETS` (68% Core / 11% Core-Plus / 21% Satellite), `TICKER_TIERS` mapping. `Core-Bond` is a sub-tier of Core for duration management (BND, IEF, SPTL, SHY, VTIP roll up to the 68% Core total).
- **Satellite targets** — `SATELLITE_TARGETS` with per-ticker target weights within the satellite sleeve
- **Macro regime** — `MACRO_REGIME` (manually updated every 14 days), `REGIME_PLAYBOOK` with 4 regimes (Stagflation, Growth/LowInflation, Recession/Deflation, Risk-Off/Transition) each defining `bond_sleeve` weights, `bond_duration_target`, and `satellite_overrides`
- **Rebalancing rules** — `drift_threshold` (3%), `max_position_pct` (10%), `review_cycle_days` (14)
- **Entry/exit signals** — `SIGNAL_RULES` with P/E thresholds and stop-loss/take-profit levels

`MACRO_REGIME['regime']` is the key field that drives which playbook is active — update it manually every 14-day review cycle.

## Inter-Stage Data Contracts

`extract_hybrid()` / `extract_yf_only()` / `extract_offline()` → `raw_data` dict:
- `raw_data['positions']` — DataFrame with columns: `symbol`, `shares`, `avg_cost`, `latest_price`, `market_value`, `cost_basis`, `unrealized_pnl`, `pe_ttm`
- `raw_data['account']` — dict with `total_equity`, `cash_balance`, `buying_power`, `unrealized_pnl`, `timestamp`
- `raw_data['quotes']` — DataFrame with `symbol`, `latest_price`, `pe_ttm` (and more in hybrid mode)
- `raw_data['timestamp']` — datetime of the extract

`transform_all()` → `analytics` dict:
- `analytics['holdings']` — enriched positions DataFrame with `tier`, `tier_parent`, `weight`, `drift`
- `analytics['summary']` — dict with `total_portfolio`, `core_pct`, `satellite_pct`, `total_pnl`, `total_pnl_pct`
- `analytics['rebalance']` — DataFrame with `symbol`, `signal` (TRIM/ADD/HOLD), `action`
- `analytics['macro_signals']` — DataFrame with `symbol`, `asset_class`, `action`, `urgency`
- `analytics['entry_signals']` — DataFrame with `symbol`, `entry_signal`
- `analytics['bond_duration']` — dict with `current_duration`, `target_duration`, `duration_gap`
- `analytics['satellite_corr']` — correlation matrix DataFrame

## Stale Root-Level Files

There are duplicate `.py` files at the project root (`extract.py`, `load.py`, `settings.py`) — these are old copies, not the active code. The live modules are in `modules/` and `config/`. Do not edit the root-level duplicates.

## Manual Fields to Update Each Cycle

In `config/settings.py`:
- `MACRO_REGIME['regime']` — the active playbook key (Stagflation / Growth/LowInflation / Recession/Deflation / Risk-Off/Transition)
- `MACRO_REGIME['last_updated']` — date of last regime assessment
- `MACRO_REGIME['vix']`, `['pce']`, `['notes']` — update key macro context each cycle
- `PE_5Y_AVERAGES` — refresh quarterly for accurate entry/exit signals
- `WATCHLIST` — add/resolve pending actions (exits, deferrals, triggers) each cycle

`SNAPSHOT_DATE` is used as a display label in the Excel header; update when doing a fresh data snapshot.

**After executing a trade that removes a position:** remove the ticker from `TICKER_TIERS` and `SATELLITE_TARGETS` (and `PE_5Y_AVERAGES` if applicable), then delete the corresponding `WATCHLIST` entry.

## Adding a New Ticker

1. Add to `TICKER_TIERS` in `config/settings.py`
2. If satellite: add to `SATELLITE_TARGETS` with a weight (0.07 default)
3. If satellite: add to `PE_5Y_AVERAGES`
4. Add display name to `name_map` dict in `modules/load.py`

## Testing

No test suite exists. Primary dev feedback loop:
```bash
python main.py --yf-only   # live prices, no Tiger credentials needed, ~15 seconds
python main.py --offline   # instant, uses latest saved snapshot
```

## Deployment

Runs on a Synology NAS via cron every 14 days:
```bash
0 20 */14 * * cd /volume1/investments/tiger_portfolio && python3 main.py
```
