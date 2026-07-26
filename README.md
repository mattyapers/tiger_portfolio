# Tiger Portfolio Tracker

A rules-based portfolio management pipeline for a Singapore-based investor, covering **two books from one repo**: a Core (86%) / Core-Plus (14%) long-term passive buy-and-hold book, and a Satellite/active-thesis risk book. Generates both an interactive Excel report and a self-contained HTML dashboard for each.

> **Split 2026-07-24:** This project used to run one blended Core (68%) / Core-Plus (11%) / Satellite (21%) allocation. It's now two logical books sharing one codebase: `python main.py` runs Core/Core-Plus (`config/settings.py`), `python main.py --satellite` runs the Satellite/risk book (`config/settings_satellite.py`). Same Tiger Brokers account, same `modules/` code — each book only totals its own slice of `TICKER_TIERS`, so the two never blend into one pie or double-count each other's positions. See [Two Books, One Repo](#two-books-one-repo) below. Core/Core-Plus targets above are the original 68/11 ratio rescaled to sum to 100% now that Satellite has its own book.

**Author:** Matthew  
**Last Updated:** 2026-07-24 (Core/Core-Plus + Satellite split into two books, one repo)  
**Python:** 3.12+ on Windows  

---

## Quick Start

```bash
# Install dependencies
pip install tigeropen yfinance pandas openpyxl numpy

# Core/Core-Plus book (default): live Tiger positions + live yfinance prices
python main.py

# Satellite/risk book instead — same account, different config
python main.py --satellite

# Test without Tiger credentials (offline shares, live prices) — combine with --satellite too
python main.py --yf-only

# Fully offline (no internet — uses latest auto-saved snapshot)
python main.py --offline
```

Output: `output/portfolio_tracker.xlsx` + `output/dashboard.html` (Core/Core-Plus), or `output/satellite_tracker.xlsx` + `output/satellite_dashboard.html` (`--satellite`) — see [Two Books, One Repo](#two-books-one-repo).

---

## How the Pipeline Works

```
main.py (orchestrator)
  │
  ├─ STAGE 1: extract.py ─── Tiger API (what you OWN)
  │                       └── yfinance  (what it's WORTH)
  │                       └── merge + fix fractional shares
  │                       └── auto-save → output/latest_snapshot.json
  │
  ├─ STAGE 2: transform.py ─ classify tiers
  │                        ├─ calculate weights + drift
  │                        ├─ generate rebalance signals
  │                        └─ score entry/exit opportunities
  │
  ├─ STAGE 2b: screener.py ─ fetch WATCHLIST tickers from yfinance
  │                        ├─ score P/E vs 5Y avg + FCF yield
  │                        └─ score Quadrant D regime fit (skipped offline)
  │
  ├─ STAGE 3: load.py ───── write Excel (formulas, not hardcodes)
  │                       └── 7 sheets: Dashboard, Holdings, Rebalance
  │                           Signals, Entry Signals, Audit, Watchlist,
  │                           Screener
  │
  └─ STAGE 4: dashboard.py ── fetch technical data (RSI, MAs, 52W range)
                             ├─ fetch macro data (CPI, unemployment, yields)
                             └─ generate self-contained HTML dashboard
```

**Data flow:** Every file passes data forward as DataFrames or dicts. `settings.py` (or `settings_satellite.py` under `--satellite`) is imported once by `main.py` and passed as a parameter into every stage — it's the single source of truth for rules, thresholds, and targets, and no other module imports it directly.

---

## File Map

```
tiger_portfolio/
├── main.py                  ← Run this. --satellite picks the other book. Orchestrates extract → transform → load.
├── config/
│   ├── settings.py            ← Core/Core-Plus book: rules, targets, thresholds, API credentials.
│   ├── settings_satellite.py  ← Satellite/risk book: same shape, different tickers/targets/output paths.
│   ├── tiger_private_key.pem  ← RSA key for Tiger API auth (NEVER commit to git). Same key, both books.
│   └── __init__.py
├── modules/                  ← Shared by both books — no ticker names hardcoded here, all driven by settings.
│   ├── extract.py           ← Stage 1: Pull data from Tiger + yfinance.
│   ├── transform.py         ← Stage 2: Calculate metrics, generate signals. classify_tiers() drops anything not in the active book's TICKER_TIERS.
│   ├── screener.py          ← Stage 2b: Fetch + score WATCHLIST tickers (skipped offline).
│   ├── load.py              ← Stage 3: Write Excel workbook.
│   ├── dashboard.py         ← Stage 4: Generate HTML portfolio dashboard.
│   ├── audit.py             ← Data freshness + price-drift checks (written to Audit sheet).
│   └── __init__.py
├── output/
│   ├── portfolio_tracker.xlsx    ← Core/Core-Plus Excel report (7 sheets).
│   ├── satellite_tracker.xlsx    ← Satellite Excel report (`--satellite`), separate file.
│   ├── dashboard.html            ← Core/Core-Plus HTML dashboard.
│   ├── satellite_dashboard.html  ← Satellite HTML dashboard (`--satellite`).
│   ├── latest_snapshot.json      ← Core/Core-Plus auto-saved snapshot.
│   ├── satellite_snapshot.json   ← Satellite auto-saved snapshot (`--satellite`).
│   └── run_{core|satellite}_YYYYMMDD_HHMM.log  ← Log file per run, tagged by book.
├── prompts/
│   ├── stage0_freshness_check.md  ← Paste into Claude: staleness triage (no web search).
│   ├── stage1_macro_regime.md     ← Paste into Claude: fetch macro data + generate MACRO_REGIME dict.
│   └── stage2_weekly_review.md    ← Paste into Claude: full weekly portfolio review (attach xlsx).
└── README.md                ← You are here.
```

---

## Two Books, One Repo

**Why:** Core/Core-Plus is long-term, passive, buy-and-hold. Satellite is active and thesis-driven. Blending them into one 68/11/21 allocation meant Satellite's per-position P/E scores and trim triggers cluttered the passive book's dashboard, and sizing was hard to reason about ("Satellite is 21% of everything, GLDM is 15% of Satellite" — what's GLDM really, as a fraction of net worth?). Splitting into two books means the numbers you see ARE the real sizing: GLDM at 15% in the Satellite book means 15% of that book, full stop.

**How it works, mechanically:**
- Same Tiger Brokers account, same `.env`/`config/tiger_private_key.pem`, same `modules/` code
- `main.py` picks `config/settings.py` by default, or `config/settings_satellite.py` when you pass `--satellite`
- Each settings module has a disjoint `TICKER_TIERS` — Core/Core-Plus/Core-Bond tickers in one, Satellite tickers in the other
- `modules/transform.py`'s `classify_tiers()` drops any position not in the active book's `TICKER_TIERS` (tier `Unknown`) before computing totals — this is what stops the two books' positions from bleeding into each other's weight/drift math when they share one account
- Separate `OUTPUT_PATH` / `SNAPSHOT_PATH` / `DASHBOARD_PATH` per book (set in each settings module) so running both never overwrites the other's files

**Known gap:** 1 share of `MRVL` (cost $300.34) is held in the account but isn't in either book's `TICKER_TIERS` — invisible to both books' totals until added to one of them (or tracked manually). See the `MRVL` note in `WATCHLIST` in `config/settings_satellite.py`.

---

## Excel Sheets

`output/portfolio_tracker.xlsx` contains 7 sheets, written in this order:

| Sheet | Source | Purpose |
|-------|--------|---------|
| 📊 Dashboard | transform + settings | Tier weights, P&L summary, macro regime, next review date |
| 📈 Holdings | extract + transform | All positions — price (blue/editable), shares, P&L, weight vs target |
| ⚖️ Rebalance Signals | transform | Satellite drift signals: TRIM/ADD/HOLD, shares to trade, est. proceeds — **renders empty in the Core/Core-Plus book**; populated when run with `--satellite` |
| 🎯 Entry Signals | transform | P/E scoring (1–5), stop-loss flags, entry/exit signals per position — **renders empty here**, same reason |
| 📋 Audit | audit | Data freshness table + price drift vs snapshot (>10% flagged) |
| 👀 Watchlist | settings.WATCHLIST | All pending actions — **renders empty in the Core/Core-Plus book** (`WATCHLIST = {}` in `config/settings.py`); active theses live in `config/settings_satellite.py`, populated when run with `--satellite` |
| 🔍 Screener | screener + yfinance | WATCHLIST tickers: P/E TTM, Fwd P/E, 5Y avg, premium, FCF yield, Quadrant D regime fit — **renders empty here**, same reason as Watchlist |

The **Screener** sheet is populated in hybrid and yf-only modes when `WATCHLIST` has entries. In `--offline` mode, or here (empty `WATCHLIST`), it renders empty with a notice. Tickers without a `PE_5Y_AVERAGES` entry show `—` for premium — the row still renders. Tickers that fail yfinance fetch show `ERR` in the Signal column.

---

## Three Run Modes

| Mode | Command | Tiger API | yfinance | When to use |
|------|---------|-----------|----------|-------------|
| **Hybrid** (default) | `python main.py` | Positions | Prices + P/E | Normal workflow — most accurate |
| **YF-Only** | `python main.py --yf-only` | Not used | Prices + P/E | Testing without Tiger credentials |
| **Offline** | `python main.py --offline` | Not used | Not used | No internet, uses last snapshot |

### How offline stays fresh

Every time you run `--hybrid` or `--yf-only`, the pipeline auto-saves your positions + prices to `output/latest_snapshot.json`. When you run `--offline`, it reads this snapshot instead of stale hardcoded data. So as long as you run the live pipeline periodically, offline mode stays current.

If `latest_snapshot.json` doesn't exist (first run ever), offline falls back to hardcoded data in `extract.py`.

---

## HTML Dashboard

The pipeline generates a **self-contained HTML dashboard** (`output/dashboard.html`) with 4 sections:

- **Portfolio Overview** — Total equity, P&L, allocation by tier (Core/Bonds/Satellite), doughnut chart
- **Stock Deep-Dive Cards** — Per holding: shares, cost basis, P/E, gain/loss %, progress bar
- **Macro Monitor** — CPI, PCE, unemployment, Fed funds rate, GDP growth, Treasury yields (10Y/2Y), yield curve, DXY
- **Technical Snapshot** — Per holding: 52W high/low, moving averages (50/200-day), RSI (14-day), overbought/oversold flags

**Features:**
- Near self-contained (~73KB HTML) — works offline after initial generation (loads Chart.js from CDN on first open)
- Single external dependency: Chart.js via free CDN (inline fallback is inline data)
- Interactive allocation chart with hover tooltips
- Color-coded metrics (green for gains, red for losses)
- Responsive design (desktop/tablet/mobile)
- Data source appendix + investment disclaimer included

Simply open `output/dashboard.html` in any web browser after running the pipeline. See [DASHBOARD_README.md](DASHBOARD_README.md) for detailed customization guide.

---

## Key Concepts

### Tier Structure

| Tier | Target | Purpose | Tickers |
|------|--------|---------|---------|
| Core | 86% | Passive index tracking | VOO, VXUS |
| Core-Bond | (part of Core) | Duration-managed bonds | SHY, VTIP, BND, IEF, SPTL |
| Core-Plus | 14% | Income + growth ETFs | SPYD, ONEQ |

Satellite (active stock picks — RTX, GLDM, GOOG, NVDA, etc.) lives in `config/settings_satellite.py`, run via `python main.py --satellite`. Entry/exit scoring, per-position P/E signals, and `SATELLITE_TARGETS` are all defined there.

### Rebalance Rules (settings.py)

- **Tier drift:** Core/Core-Plus vs. `TIER_TARGETS` — >5pp drift triggers 🚨 Rebalance, >3pp triggers ⚠️ Drifting (hardcoded in `transform.py`'s `calculate_tier_drift()`, not a `settings.py` value)
- **14-day review cycle:** Run the pipeline every 2 weeks minimum (`REBALANCE_RULES['review_cycle_days']`)
- `REBALANCE_RULES`/`SIGNAL_RULES` in `settings.py` are otherwise dormant in the Core/Core-Plus book — they only drive per-position Satellite signals, which live in `settings_satellite.py`'s copy of these dicts. Kept (not deleted) here because `load.py`/`transform.py` reference them unconditionally regardless of which book is active.

### Macro Regime (manual input)

The `MACRO_REGIME` dict in settings.py drives the dashboard and the `REGIME_PLAYBOOK`'s Core-Bond duration target. Update it at each 14-day review. (`settings_satellite.py` keeps its own copy of `MACRO_REGIME` — same content, updated at the same time — plus its own `REGIME_PLAYBOOK` with `satellite_overrides` instead of bond fields.)

**Current regime (2026-07-24):** Stagflation / Hike-Risk Escalating — Hormuz Effectively Closed, Oil Shock Underway | Quadrant D, high confidence. Hormuz effectively closed Jul 11-23 (only 15 ships transited Jul 19 vs ~88/day normal). Brent broke $100 intraday for the first time in 2 months. Fed hike risk resurfaced to ~35% for the Jul 29 FOMC (from near-zero). See `config/settings.py`'s `MACRO_REGIME` dict for full detail.

**Quadrant B watch:** Two conditions required to rotate — (1) Fed balance sheet > $7T (currently $6.736T, $264B away), (2) Dec cut prob > 30% (currently ~15.4%). Still far.

---

## Common Workflows

### After executing a trade

1. Run `python main.py` (hybrid mode auto-pulls new positions from Tiger)
2. Check output Excel — verify new shares and signals
3. Snapshot auto-saves for future offline use

### 14-day review cycle

1. Run `python main.py`
2. Run the three-stage Claude review (see [Weekly Review Workflow](#weekly-review-workflow) below)
3. Paste updated `MACRO_REGIME` dict from Stage 1 into `config/settings.py`
4. Review Dashboard sheet: tier drift, macro regime
5. Review Rebalance Signals: any BREACH/TRIM/ADD?
6. Review Entry Signals: any score 1 (entry) or score 5 (trim)?
7. Check `WATCHLIST` in settings.py for pending actions (exits, deferrals, triggers)
8. Log decisions in Notion checklist

### Adding a new ticker

For Core/Core-Plus/Core-Bond, edit `config/settings.py`. For a new active/thesis-driven satellite position, edit `config/settings_satellite.py` instead — same steps, different file.

1. Add to `TICKER_TIERS` (Core book: `Core` / `Core-Bond` / `Core-Plus`; Satellite book: `Satellite`)
2. Satellite book only: add to `SATELLITE_TARGETS` (rebalance the others so it still sums to 1.00) and `PE_5Y_AVERAGES`
3. Add display name to `name_map` dict in load.py
4. Run pipeline to verify (`python main.py` or `python main.py --satellite`)

### Adding a ticker to the Watchlist

The Core/Core-Plus book's `WATCHLIST` is intentionally empty — passive index exposure has no active entry/exit theses to track. Add new watchlist candidates to `config/settings_satellite.py` instead:

1. Add entry to `WATCHLIST` in settings_satellite.py (fields: `ticker`, `action`, `note`, optional `target_price` / `trigger_date`)
2. Add a `WATCHLIST_REGIME_FIT` entry: `{'score': '✅|⚠️|❌', 'reason': '...'}`
3. If a 5Y P/E average is available: add to `PE_5Y_AVERAGES` (optional — omitting shows `—` for premium, row still renders)
4. Run pipeline — ticker appears in Watchlist and Screener sheets automatically

---

## Weekly Review Workflow

The `prompts/` directory contains three Claude prompts that form a structured review pipeline. Run them in order each cycle (Sunday evening or Monday morning).

| Stage | File | Purpose | Inputs | Outputs |
|-------|------|---------|--------|---------|
| **Stage 0** | `stage0_freshness_check.md` | Staleness triage | `DATA_FRESHNESS` dict, `MACRO_REGIME['as_of_date']`, last log timestamp | ✅/⚠️/🚨 verdict, carry-forward 🔴 items |
| **Stage 1** | `stage1_macro_regime.md` | Macro data fetch | Web search (Brent, VIX, FedWatch, H.4.1, PCE, yields, Hormuz, Sec122, MAS) | Regime call + paste-ready `MACRO_REGIME` dict |
| **Stage 2** | `stage2_weekly_review.md` | Full portfolio review | Stage 1 regime + attached `portfolio_tracker.xlsx` | Scorecard, health check, regime-fit, action plan |

### How to run

**Stage 0** (no internet needed — deterministic):
1. Open a new Claude conversation
2. Paste the full contents of `prompts/stage0_freshness_check.md`
3. Append the `DATA_FRESHNESS` dict and `MACRO_REGIME` block from `config/settings.py`
4. If verdict is RED: update stale fields in `settings.py` before continuing

**Stage 1** (requires web search):
1. Open a new Claude conversation
2. Paste the full contents of `prompts/stage1_macro_regime.md`
3. Copy the output `MACRO_REGIME` dict into `config/settings.py` → rerun `python main.py`

> **Key mapping note:** The Stage 1 dict uses shortened keys (`ffr`, `bs`, `pce_h`, `pce_c`, `fw_next`, `fw_dec`, `b_dist`). Map these to the full key names already present in `config/settings.py` when pasting — don't overwrite the existing key structure.

**Stage 2** (requires the Excel output):
1. Open a new Claude conversation
2. Paste the full contents of `prompts/stage2_weekly_review.md`
3. Update the `## CURRENT REGIME` block with the Stage 1 regime call
4. Attach `output/portfolio_tracker.xlsx`

### Supplementary Finance Skills

These are global Claude Code plugins (user scope — available in every session, not a Python dependency, not part of this repo). They supplement the Stage 0/1/2 workflow above; `prompts/*.md` stay static and unmodified.

| Plugin | Source | Helps with |
|---|---|---|
| `finance-market-analysis` | `himself65/finance-skills` | DCF/relative/SOTP valuation, earnings preview/recap, ETF premium-discount — use when refreshing `PE_5Y_AVERAGES` instead of manual Macrotrends web search |
| `financial-analysis` | `claude-for-financial-services` | Core DCF/comps/LBO/3-statement modeling primitives underlying the verticals below |
| `equity-research` | `claude-for-financial-services` | `/comps`, `/earnings` — resolving `WATCHLIST` catalyst items (e.g. `MSFT_WATCH` Azure-growth check, `CAT_TRIM` thesis re-check) |
| `wealth-management` | `claude-for-financial-services` | Client-review/reporting skills — maps onto Stage 2's Portfolio Health Check and Action Recommendations sections |
| `investment-banking` | `claude-for-financial-services` | Pitch decks, comps/LBO, transaction management — installed but lower relevance to a personal portfolio tracker |

### Stage 0 verdict logic

| Verdict | Meaning | Action |
|---------|---------|--------|
| GREEN | All data fresh | Skip to Stage 1 |
| YELLOW | Some items due soon | Run Stage 1, then Stage 2 |
| RED | Stale data present | Update `settings.py` first, then rerun pipeline |

---

## Fractional Share Bug (Fixed)

Tiger's free tier sometimes reports fractional shares as integers (0.6849 → 6849). The hybrid pipeline auto-detects this: if `tiger_shares × yf_price` is more than 5x `tiger_market_value`, it recalculates shares as `tiger_market_value / yf_price`. No manual intervention needed.

---

## Dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| tigeropen | Tiger Brokers API | `pip install tigeropen` |
| yfinance | Free market data (prices, P/E) | `pip install yfinance` |
| pandas | DataFrames, data manipulation | `pip install pandas` |
| openpyxl | Excel read/write | `pip install openpyxl` |
| numpy | Numerical calculations | `pip install numpy` |

---

## Security

- **Never commit** `tiger_private_key.pem` to GitHub
- **Never commit** real `TIGER_ID` or `ACCOUNT` values
- The `.gitignore` should include: `config/tiger_private_key.pem`, `output/`, `*.log`
- The `settings.py` in the public repo should have placeholder credentials

---

## Singapore Tax Advantage

Zero capital gains tax in Singapore. This is a structural edge — every rebalance, trim, and rotation incurs zero tax friction. The pipeline is designed to exploit this by recommending frequent, small rebalances rather than waiting for large drifts.

---

## Notion Integration

Operational checklists and execution plans live in Notion under the Investing workspace. Key pages:
- **Investing Rules & Checklists** — weekly/monthly/quarterly review templates
- **3-Tranche DCA Execution Plan** — current deployment plan with override log

---

## Pending Actions

None in the Core/Core-Plus book — `WATCHLIST` here is intentionally empty (passive only). All open items (BABA exit, XLE entry, CAT trim, MSFT watch, Quadrant B candidates) live in `config/settings_satellite.py`'s `WATCHLIST` — run `python main.py --satellite` and check that book's Watchlist sheet.

## Future Roadmap

- [x] HTML dashboard with 4 integrated sections (Portfolio Overview, Stock Cards, Macro Monitor, Technical)
- [x] Watchlist sheet — renders WATCHLIST dict with action, target price, date, note
- [x] Screener sheet — WATCHLIST valuation + Quadrant D regime-fit scoring
- [ ] Deploy to Synology NAS for automated daily runs
- [ ] Add correlation matrix sheet to Excel output
- [ ] Bond duration calculator sheet
- [ ] Extend technical indicators (Bollinger Bands, MACD, volume analysis)
- [ ] Add portfolio performance charts (daily/weekly/monthly returns)
- [ ] Automated Notion updates via MCP after each pipeline run