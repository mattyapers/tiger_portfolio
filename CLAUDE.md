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

**Split 2026-07-24:** This repo now runs **two books from one codebase**: Core + Core-Plus (default, `config/settings.py`) and Satellite/active-risk (`python main.py --satellite`, `config/settings_satellite.py`). Same Tiger account, same `modules/` code, disjoint `TICKER_TIERS` per book. `modules/transform.py`'s `classify_tiers()` drops anything not in the active book's `TICKER_TIERS` before computing totals — that's what keeps the two books from double-counting each other's positions. Each book has its own `OUTPUT_PATH`/`SNAPSHOT_PATH`/`DASHBOARD_PATH` so running both never overwrites the other's files.

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

1. **Extract** (`modules/extract.py`) — `extract_hybrid()` authenticates with Tiger (RSA-signed), fetches positions, overlays live prices + P/E from yfinance. Auto-fixes fractional share inflation (`real_shares = tiger_market_value / yf_price`). `extract_yf_only()` uses snapshot/hardcoded shares + yfinance. `extract_offline()` loads `settings.SNAPSHOT_PATH`, falls back to `_extract_hardcoded()`. Saves snapshot to `settings.SNAPSHOT_PATH` (differs per book).
2. **Transform** (`modules/transform.py`) — Pure data. Produces tier classification (`Core` / `Core-Bond` / `Core-Plus` in the default book; `Satellite` in the `--satellite` book — the two never coexist since each book's `TICKER_TIERS` only contains its own tickers), weights + drift vs targets, rebalance signals (`TRIM` / `ADD` / `HOLD` at 3% threshold — dormant in the Core/Core-Plus book, no Satellite tier there), macro-regime playbook signals, P/E entry/exit scores (1-5, also dormant in the Core/Core-Plus book). `classify_tiers()` drops any position not in the active book's `TICKER_TIERS` (tier `Unknown`) before totals are computed — this is what lets both books share one Tiger account without double-counting each other's holdings.
2b. **Screener** (`modules/screener.py`) — `run_screener()` extracts unique tickers from `WATCHLIST`, fetches live yfinance data (price, trailing P/E, forward P/E, FCF yield), computes P/E premium vs `PE_5Y_AVERAGES`, scores each ticker against `WATCHLIST_REGIME_FIT` for Quadrant D fit. Skipped in `--offline` mode; returns empty DataFrame in the Core/Core-Plus book regardless (`WATCHLIST = {}` there).
3. **Load** (`modules/load.py`) — `openpyxl`. Seven sheets: Dashboard, Holdings, Rebalance Signals, Entry Signals, Audit, Watchlist, Screener. Blue = editable inputs; black = Excel formulas; yellow = flags.
4. **Dashboard** (`modules/dashboard.py`) — Self-contained HTML with Portfolio Overview (doughnut), Stock Deep-Dive Cards, Macro Monitor (CPI, PCE, unemployment, Fed funds, GDP, Treasury yields 10Y/2Y, yield curve, DXY), Technical Snapshot (52W H/L, distance, 50/200 MA, RSI 14, flags). Inline CSS/JS + data-source appendix + investment disclaimer. Reads `output/latest_snapshot.json`.

---

## Configuration

Two settings modules, same shape, loaded by `main.py` based on the `--satellite` flag. No hardcoding in `modules/` — both books share every module.

**`config/settings.py`** (Core/Core-Plus book, default):
- `TIGER_ID`, `ACCOUNT`, `PRIVATE_KEY_PATH`, `LICENSE` — same Tiger account as `settings_satellite.py`
- `TIER_TARGETS` (86% Core / 14% Core-Plus — rescaled from the original 68/11 ratio after Satellite got its own book), `TICKER_TIERS` (mapping; `Core-Bond` sub-tier rolls into Core: BND, IEF, SPTL, SHY, VTIP)
- `SATELLITE_TARGETS`, `PE_5Y_AVERAGES`: kept as **empty dicts**, not deleted — `load.py`/`transform.py` reference them unconditionally regardless of tier content. Real values live in `settings_satellite.py`.
- `MACRO_REGIME`: same content as `settings_satellite.py`'s copy (both updated together every 14 days) — still relevant here for the Core-Bond duration target
- `REGIME_PLAYBOOK`: regime definitions (`bond_sleeve`, `bond_duration_target`) — no `satellite_overrides` key here, that lives in `settings_satellite.py`
- `REBALANCE_RULES`/`SIGNAL_RULES`: kept but **dormant** — they only drive per-position Satellite signals, and this book has no Satellite tier
- `WATCHLIST` / `WATCHLIST_REGIME_FIT`: intentionally **empty** — passive Core/Core-Plus has no active theses to track
- `OUTPUT_PATH`/`SNAPSHOT_PATH`/`DASHBOARD_PATH`: `output/portfolio_tracker.xlsx` / `output/latest_snapshot.json` / `output/dashboard.html`

**`config/settings_satellite.py`** (Satellite/risk book, `--satellite`):
- Same credential fields, same Tiger account
- `TIER_TARGETS = {'Satellite': 1.00}` — single tier, this book IS the whole risk portfolio
- `TICKER_TIERS`, `SATELLITE_TARGETS`, `PE_5Y_AVERAGES`: the real per-position config for every active/thesis-driven ticker
- `REGIME_PLAYBOOK`: only `satellite_overrides` per regime — no bond fields, no bond sleeve in this book
- `WATCHLIST` / `WATCHLIST_REGIME_FIT`: the full active-thesis list (all entries that used to live in the single blended `settings.py`)
- `OUTPUT_PATH`/`SNAPSHOT_PATH`/`DASHBOARD_PATH`: `output/satellite_tracker.xlsx` / `output/satellite_snapshot.json` / `output/satellite_dashboard.html` — deliberately different files so running both books never overwrites the other
- `SNAPSHOT_DATE`: display label in Excel header (both modules have their own)

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

Run three-stage prompt workflow first (see [Prompts Directory](#prompts-directory)), then edit **both** settings modules (`MACRO_REGIME` is duplicated, update both copies together):

`config/settings.py`:
- [ ] `MACRO_REGIME` — paste dict output from Stage 1 prompt
- [ ] `SNAPSHOT_DATE` — if fresh snapshot

`config/settings_satellite.py`:
- [ ] `MACRO_REGIME` — same paste as above
- [ ] `PE_5Y_AVERAGES` — quarterly refresh
- [ ] `WATCHLIST` — resolve/add actions
- [ ] `WATCHLIST_REGIME_FIT` — update scores if regime or thesis changes
- [ ] `SNAPSHOT_DATE` — if fresh snapshot

After removing a Core/Core-Plus position: remove from `TICKER_TIERS` in `config/settings.py`.
After removing a Satellite position: remove from `TICKER_TIERS`/`SATELLITE_TARGETS`/`PE_5Y_AVERAGES` in `config/settings_satellite.py`, delete its `WATCHLIST` entry.

---

## Prompts Directory

`prompts/` contains three Claude prompts for the weekly review cycle, chained: Stage 0's output feeds Stage 1's open questions; Stage 1's rendered output pastes verbatim into Stage 2's CURRENT REGIME section (field order matches on purpose — no manual reformatting step between them). Run in order each 14-day cycle, against **both** settings modules — the pipeline is a two-book system now, not one.

| File | Stage | Role | Key constraint |
|---|---|---|---|
| `stage0_freshness_check.md` | 0 | Staleness + desync triage | No web search; deterministic logic only; reads DATA_FRESHNESS/MACRO_REGIME from both `settings.py` and `settings_satellite.py`, flags it if the two MACRO_REGIME copies disagree |
| `stage1_macro_regime.md` | 1 | Macro data fetch | Outputs a paste-ready `MACRO_REGIME` dict for **both** settings modules (same content, duplicated field) + a rendered block for Stage 2 |
| `stage2_weekly_review.md` | 2 | Full portfolio review | Requires both `output/portfolio_tracker.xlsx` and `output/satellite_tracker.xlsx` attached |

Stage 0 verdict gates the rest: GREEN skips to Stage 1; RED means update stale/desynced fields before continuing.

Stage 1 dict uses shortened keys (`ffr`, `bs`, `pce_h`, `pce_c`, `fw_next`, `fw_dec`, `b_dist`) — map to full key names already in both settings modules when pasting.

**These files are living documents, not static templates** — each stage is responsible for bumping the `DATA_FRESHNESS['...']['value']` entry it just refreshed (in both settings modules where the field is shared) as its last step. A stage that reads/confirms data without bumping the corresponding freshness value leaves next cycle's Stage 0 blind to the fact a review happened — that's the main failure mode this chaining is designed to close. Edit `stage2_weekly_review.md`'s CURRENT REGIME section weekly (Stage 1 output goes there); edit `stage0`/`stage1` only when the process itself needs to change (as done 2026-07-28 to make the three stages dual-book aware).

---

## External Finance Skills

Installed globally (user scope, all Claude Code sessions — not project config, so nothing here lives in this repo):

| Plugin | Source | Use for |
|---|---|---|
| `finance-market-analysis` | `himself65/finance-skills` | DCF/relative/SOTP valuation, earnings preview/recap, ETF premium-discount, correlation, SEPA/Minervini trend-template screening — via yfinance |
| `financial-analysis` | `claude-for-financial-services` | Core DCF/comps/LBO/3-statement modeling primitives (foundation for the verticals below) |
| `equity-research` | `claude-for-financial-services` | `/comps`, `/earnings`, initiating-coverage workflows |
| `wealth-management` | `claude-for-financial-services` | Client reviews, portfolio analysis, client reporting |
| `investment-banking` | `claude-for-financial-services` | Pitch decks, comps/LBO, transaction management — installed but not central to this project |

These are a **supplement** to the `prompts/` workflow, not a replacement — `prompts/*.md` stay static/untouched. Most of the concrete use cases below (`PE_5Y_AVERAGES` refresh, `WATCHLIST` catalyst resolution) apply to **`config/settings_satellite.py`**, since that's where those fields live post-split:
- Refreshing `PE_5Y_AVERAGES` (quarterly, in `settings_satellite.py`) — `finance-market-analysis`'s DCF/relative/SOTP triangulation beats scraping Macrotrends by hand
- Resolving `WATCHLIST` catalyst items (in `settings_satellite.py`) — `equity-research`'s `/earnings` and comps workflows
- Checking a watchlist ticker's technical setup — `finance-market-analysis:sepa-strategy` (Minervini trend-template/stage/RS/base-pattern). Paste results into that ticker's `WATCHLIST[key]['sepa']` dict (`stage`, `rs_pct`, `pattern`, `checked_date`) in `settings_satellite.py`, not the free-text `note` — the Watchlist sheet renders `sepa` as its own columns (Excel truncates `note` to 200 chars, SEPA detail doesn't survive there)
- Writing up Stage 2's Portfolio Health Check / Action Recommendations (either book) — `wealth-management`'s client-review and reporting skills map onto that deliverable format

---

## Adding a New Ticker

For Core/Core-Plus/Core-Bond, edit `config/settings.py`. For a new active/satellite position, edit `config/settings_satellite.py` instead — same steps, different file, plus `SATELLITE_TARGETS`/`PE_5Y_AVERAGES` entries.

1. Add to `TICKER_TIERS` in the relevant settings module (`Core` / `Core-Bond` / `Core-Plus` in `settings.py`; `Satellite` in `settings_satellite.py`)
2. Add display name to `name_map` in @modules/load.py (shared by both books)

---

## Testing

No suite. Dev loop:
```bash
python main.py --yf-only               # Core/Core-Plus book, ~15s, no keys
python main.py --offline                # Core/Core-Plus book, instant
python main.py --satellite --yf-only    # Satellite book, ~15s, no keys
python main.py --satellite --offline    # Satellite book, instant
```

Expected outputs (Core/Core-Plus): `output/portfolio_tracker.xlsx`, `output/latest_snapshot.json`, `output/run_core_YYYYMMDD_HHMM.log`.
Expected outputs (`--satellite`): `output/satellite_tracker.xlsx`, `output/satellite_snapshot.json`, `output/run_satellite_YYYYMMDD_HHMM.log`.

---

## Common Issues

| Symptom | Fix |
|---|---|
| `FileNotFoundError: latest_snapshot.json` (or `satellite_snapshot.json`) | Run `--yf-only` (add `--satellite` for that book) first; check `output/`. |
| Tiger auth failure | Verify `config/tiger_private_key.pem` and `TIGER_ID`/`ACCOUNT` — same `.env` drives both settings modules. |
| Excel `#REF!` | Ticker removed from `TICKER_TIERS` but still referenced; clean mapping in the relevant settings module. |
| Dashboard missing data | Ensure the book's snapshot file exists (`SNAPSHOT_PATH`); regenerate if needed. |
| A satellite ticker shows up in the Core/Core-Plus book (or vice versa) | Check `TICKER_TIERS` in both settings modules for an accidental duplicate — should always be disjoint. |

---

## Protected Areas

- Do not edit root `extract.py`, `load.py`, `settings.py` (stale). Use `modules/` and `config/`.
- Do not edit or commit `config/tiger_private_key.pem` or `.env`.
- Do not hand-edit `output/latest_snapshot.json` or `output/satellite_snapshot.json` (overwritten each run).
- All tunables must remain in `config/settings.py` / `config/settings_satellite.py`; no hardcoding in `modules/`.
- Keep `TICKER_TIERS` disjoint between the two settings modules — a ticker in both would get counted twice across the two books.
