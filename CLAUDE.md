# CLAUDE.md

Guide for Claude Code in this repo.

## Contents
1. [Overview](#what-this-project-does)
2. [Quick Commands](#quick-commands)
3. [File Layout](#file-layout)
4. [Dependencies](#dependencies)
5. [Architecture](#architecture)
6. [Config](#configuration)
7. [Data Contracts](#inter-stage-data-contracts)
8. [Manual Updates](#manual-update-checklist-every-14-day-cycle)
9. [Prompts](#prompts-directory)
10. [External Skills](#external-finance-skills)
11. [Add Ticker](#adding-a-new-ticker)
12. [Testing](#testing)
13. [Issues](#common-issues)
14. [Protected Areas](#protected-areas)

---

## What This Project Does

Tiger Portfolio Tracker: Python ETL for automated portfolio management. Tiger Brokers API (Singapore brokerage) + yfinance prices. Calculates allocation drift + macro-regime signals. Writes Excel report (`output/portfolio_tracker.xlsx`) and HTML dashboard (`output/dashboard.html`).

---

## Quick Commands

| Command | Mode | Needs API? | Time |
|---|---|---|---|
| `python main.py` | Hybrid (default) | Yes | ~30s |
| `python main.py --yf-only` | Offline shares + yfinance | No | ~15s |
| `python main.py --offline` | Latest snapshot | No | Instant |
| `python modules/dashboard.py` | Standalone HTML | No | ~5s |

Artifacts: `output/portfolio_tracker.xlsx`, `output/latest_snapshot.json`, `output/run_YYYYMMDD_HHMM.log`.

---

## File Layout

```
.
├── main.py                 # Orchestrator
├── modules/
│   ├── extract.py          # Stage 1 (hybrid / yf-only / offline)
│   ├── transform.py        # Stage 2 (pure data, no I/O)
│   ├── screener.py         # Stage 2b (WATCHLIST yfinance fetch + regime-fit scoring)
│   ├── load.py             # Stage 3 (Excel via openpyxl — 7 sheets)
│   ├── dashboard.py        # Stage 4 (HTML, Chart.js CDN)
│   └── audit.py            # Data freshness + price-drift checks (called by transform)
├── config/
│   └── settings.py         # All tunables + credential refs
├── prompts/
│   ├── stage0_freshness_check.md   # Staleness triage (no web search)
│   ├── stage1_macro_regime.md      # Macro fetch + MACRO_REGIME dict output
│   └── stage2_weekly_review.md     # Full weekly review (attach xlsx)
└── output/
    ├── latest_snapshot.json
    ├── portfolio_tracker.xlsx
    └── dashboard.html
```

> **Stale duplicates at root**: `extract.py`, `load.py`, `settings.py` are old copies. Live code is `modules/` and `config/`. Do not edit root `.py` files.

---

## Dependencies

```bash
pip install tigeropen yfinance openpyxl pandas numpy
```
Python 3.9+. Credentials in `config/`: `tiger_private_key.pem` (RSA private key). Never commit.

---

## Architecture

Sequential stages called by `main.py`:

1. **Extract** (`modules/extract.py`) — `extract_hybrid()` authenticates with Tiger (RSA-signed), fetches positions, overlays live prices + P/E from yfinance. Auto-fixes fractional share inflation (`real_shares = tiger_market_value / yf_price`). `extract_yf_only()` uses snapshot/hardcoded shares + yfinance. `extract_offline()` loads `output/latest_snapshot.json`, falls back to `_extract_hardcoded()`. Saves snapshot.
2. **Transform** (`modules/transform.py`) — Pure data. Produces tier classification (`Core` / `Core-Bond` / `Core-Plus` / `Satellite`), weights + drift vs targets, rebalance signals (`TRIM` / `ADD` / `HOLD` at 3% threshold), macro-regime playbook signals, P/E entry/exit scores (1-5), satellite correlation matrix.
2b. **Screener** (`modules/screener.py`) — `run_screener()` extracts unique tickers from `WATCHLIST`, fetches live yfinance data (price, trailing P/E, forward P/E, FCF yield), computes P/E premium vs `PE_5Y_AVERAGES`, scores each ticker against `WATCHLIST_REGIME_FIT` for Quadrant D fit. Skipped in `--offline` mode; returns empty DataFrame.
3. **Load** (`modules/load.py`) — `openpyxl`. Seven sheets: Dashboard, Holdings, Rebalance Signals, Entry Signals, Audit, Watchlist, Screener. Blue = editable inputs; black = Excel formulas; yellow = flags.
4. **Dashboard** (`modules/dashboard.py`) — Self-contained HTML with Portfolio Overview (doughnut), Stock Deep-Dive Cards, Macro Monitor (CPI, PCE, unemployment, Fed funds, GDP, Treasury yields 10Y/2Y, yield curve, DXY), Technical Snapshot (52W H/L, distance, 50/200 MA, RSI 14, flags). Inline CSS/JS + data-source appendix + investment disclaimer. Reads `output/latest_snapshot.json`.

---

## Configuration

All tunable parameters in @config/settings.py. No hardcoding in modules.

Key fields:
- `TIGER_ID`, `ACCOUNT`, `PRIVATE_KEY_PATH`, `LICENSE`
- Portfolio: `TIER_TARGETS` (68% Core / 11% Core-Plus / 21% Satellite), `TICKER_TIERS` (mapping; `Core-Bond` sub-tier rolls into Core: BND, IEF, SPTL, SHY, VTIP)
- `SATELLITE_TARGETS` (per-ticker weights within satellite sleeve)
- `MACRO_REGIME`: `regime` (active playbook key: `Stagflation` / `Growth/LowInflation` / `Recession/Deflation` / `Risk-Off/Transition`), `last_updated`, `vix`, `pce`, `notes` — update manually every 14 days
- `REGIME_PLAYBOOK`: regime definitions (`bond_sleeve`, `bond_duration_target`, `satellite_overrides`)
- `REBALANCE_RULES`: `drift_threshold` (3%), `max_position_pct` (15%), `review_cycle_days` (14)
- `SIGNAL_RULES`: P/E thresholds (`pe_max`, `pe_premium_trim`), `stop_loss_pct` (-15%), `take_profit_pct`
- `PE_5Y_AVERAGES`: refresh quarterly
- `WATCHLIST`: pending actions; resolve each cycle. Each entry: `ticker`, `action`, `note`, optional `target_price` / `trigger_date` / `review_date` / `catalyst_date`
- `WATCHLIST_REGIME_FIT`: per-ticker Quadrant D scoring for `screener.py` — `{'score': 'yes/maybe/no', 'reason': '...'}`. Update when regime or thesis changes.
- `SNAPSHOT_DATE`: display label in Excel header

---

## Inter-Stage Data Contracts

### Extract -> `raw_data`

| Key | Type | Contents |
|---|---|---|
| `positions` | DataFrame | `symbol`, `shares`, `avg_cost`, `latest_price`, `market_value`, `cost_basis`, `unrealized_pnl`, `pe_ttm` |
| `account` | dict | `total_equity`, `cash_balance`, `buying_power`, `unrealized_pnl`, `timestamp` |
| `quotes` | DataFrame | `symbol`, `latest_price`, `pe_ttm` (+ hybrid extras) |
| `timestamp` | datetime | Extract time |

### Transform -> `analytics`

| Key | Type | Contents |
|---|---|---|
| `holdings` | DataFrame | Enriched: `tier`, `tier_parent`, `weight`, `drift` |
| `summary` | dict | `total_portfolio`, `core_pct`, `satellite_pct`, `total_pnl`, `total_pnl_pct` |
| `rebalance` | DataFrame | `symbol`, `signal` (`TRIM`/`ADD`/`HOLD`), `action` |
| `macro_signals` | DataFrame | `symbol`, `asset_class`, `action`, `urgency` |
| `entry_signals` | DataFrame | `symbol`, `entry_signal` |
| `bond_duration` | dict | `current_duration`, `target_duration`, `duration_gap` |
| `satellite_corr` | DataFrame | Correlation matrix |
| `screener` | DataFrame | WATCHLIST tickers: `symbol`, `price`, `pe_ttm`, `fwd_pe`, `pe_5y_avg`, `pe_premium_pct`, `fcf_yield_pct`, `regime_fit`, `regime_note`, `signal`. Empty in `--offline` mode. |

---

## Manual Update Checklist (Every 14-Day Cycle)

Run three-stage prompt workflow first (see [Prompts Directory](#prompts-directory)), then edit @config/settings.py:
- [ ] `MACRO_REGIME` — paste dict output from Stage 1 prompt
- [ ] `PE_5Y_AVERAGES` — quarterly refresh
- [ ] `WATCHLIST` — resolve/add actions
- [ ] `WATCHLIST_REGIME_FIT` — update scores if regime or thesis changes
- [ ] `SNAPSHOT_DATE` — if fresh snapshot

After removing a position:
- [ ] Remove from `TICKER_TIERS`
- [ ] If satellite: remove from `SATELLITE_TARGETS` and `PE_5Y_AVERAGES`
- [ ] Delete `WATCHLIST` entry

---

## Prompts Directory

`prompts/` contains three Claude prompts for weekly review cycle. Run in order each 14-day cycle. Treat as static input files — do not modify.

| File | Stage | Role | Key constraint |
|---|---|---|---|
| `stage0_freshness_check.md` | 0 | Staleness triage | No web search; deterministic logic only |
| `stage1_macro_regime.md` | 1 | Macro data fetch | Outputs paste-ready `MACRO_REGIME` dict for `config/settings.py` |
| `stage2_weekly_review.md` | 2 | Full portfolio review | Requires attached `output/portfolio_tracker.xlsx` |

Stage 0 verdict gates the rest: GREEN skips to Stage 1; RED means update stale `settings.py` fields before continuing.

Stage 1 dict uses shortened keys (`ffr`, `bs`, `pce_h`, `pce_c`, `fw_next`, `fw_dec`, `b_dist`) — map to full key names already in `config/settings.py` when pasting.

---

## External Finance Skills

Installed globally (user scope, all Claude Code sessions — not project config, so nothing here lives in this repo):

| Plugin | Source | Use for |
|---|---|---|
| `finance-market-analysis` | `himself65/finance-skills` | DCF/relative/SOTP valuation, earnings preview/recap, ETF premium-discount, correlation — via yfinance |
| `financial-analysis` | `claude-for-financial-services` | Core DCF/comps/LBO/3-statement modeling primitives (foundation for the verticals below) |
| `equity-research` | `claude-for-financial-services` | `/comps`, `/earnings`, initiating-coverage workflows |
| `wealth-management` | `claude-for-financial-services` | Client reviews, portfolio analysis, client reporting |
| `investment-banking` | `claude-for-financial-services` | Pitch decks, comps/LBO, transaction management — installed but not central to this project |

These are a **supplement** to the `prompts/` workflow, not a replacement — `prompts/*.md` stay static/untouched. Reach for these instead of ad hoc web search when:
- Refreshing `PE_5Y_AVERAGES` (quarterly) — `finance-market-analysis`'s DCF/relative/SOTP triangulation beats scraping Macrotrends by hand (this is how the 2026-07-24 refresh produced two large, uncertain P/E swings for RTX and NTR — a purpose-built valuation tool should give a more defensible number)
- Resolving `WATCHLIST` catalyst items — `equity-research`'s `/earnings` and comps workflows for things like `MSFT_WATCH`'s Azure-growth check or re-verifying `CAT_TRIM`'s thesis
- Writing up Stage 2's Portfolio Health Check / Action Recommendations — `wealth-management`'s client-review and reporting skills map onto that deliverable format

---

## Adding a New Ticker

1. Add to `TICKER_TIERS` in @config/settings.py
2. If satellite: add to `SATELLITE_TARGETS` (default 0.07)
3. If satellite: add to `PE_5Y_AVERAGES`
4. Add display name to `name_map` in @modules/load.py

---

## Testing

No suite. Dev loop:
```bash
python main.py --yf-only   # ~15s, no keys
python main.py --offline   # instant
```

Expected outputs: `output/portfolio_tracker.xlsx`, `output/latest_snapshot.json`, `output/run_YYYYMMDD_HHMM.log`. Optional dashboard: `python modules/dashboard.py`.

---

## Common Issues

| Symptom | Fix |
|---|---|
| `FileNotFoundError: latest_snapshot.json` | Run `--yf-only` first; check `output/`. |
| Tiger auth failure | Verify `config/tiger_private_key.pem` and `TIGER_ID`/`ACCOUNT` in @config/settings.py. |
| Excel `#REF!` | Ticker removed from `TICKER_TIERS` but still referenced; clean mapping. |
| Dashboard missing data | Ensure `latest_snapshot.json` exists; regenerate if needed. |

---

## Protected Areas

- Do not edit root `extract.py`, `load.py`, `settings.py` (stale). Use `modules/` and `config/`.
- Do not edit or commit `config/tiger_private_key.pem`.
- Do not hand-edit `output/latest_snapshot.json` (overwritten by Stage 1).
- All tunables must remain in @config/settings.py; no hardcoding in modules.
