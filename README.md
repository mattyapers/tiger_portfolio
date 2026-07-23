# Tiger Portfolio Tracker

A rules-based portfolio management pipeline for a Singapore-based investor running a Core (68%) / Core-Plus (11%) / Satellite (21%) allocation with a 30-year, 8% CAGR target. Generates both an interactive Excel report and a self-contained HTML dashboard.

**Author:** Matthew  
**Last Updated:** 2026-07-24 (Watchlist + Screener sheets added)  
**Python:** 3.12+ on Windows  

---

## Quick Start

```bash
# Install dependencies
pip install tigeropen yfinance pandas openpyxl numpy

# Default: live Tiger positions + live yfinance prices (recommended)
python main.py

# Test without Tiger credentials (offline shares, live prices)
python main.py --yf-only

# Fully offline (no internet — uses latest auto-saved snapshot)
python main.py --offline
```

Output: `output/portfolio_tracker.xlsx` and `output/dashboard.html`

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

**Data flow:** Every file passes data forward as DataFrames or dicts. `settings.py` is imported by all three stages — it's the single source of truth for rules, thresholds, and targets.

---

## File Map

```
tiger_portfolio/
├── main.py                  ← Run this. Orchestrates extract → transform → load.
├── config/
│   ├── settings.py          ← All rules, targets, thresholds, API credentials.
│   ├── tiger_private_key.pem← RSA key for Tiger API auth (NEVER commit to git).
│   └── __init__.py
├── modules/
│   ├── extract.py           ← Stage 1: Pull data from Tiger + yfinance.
│   ├── transform.py         ← Stage 2: Calculate metrics, generate signals.
│   ├── screener.py          ← Stage 2b: Fetch + score WATCHLIST tickers (skipped offline).
│   ├── load.py              ← Stage 3: Write Excel workbook.
│   ├── dashboard.py         ← Stage 4: Generate HTML portfolio dashboard.
│   ├── audit.py             ← Data freshness + price-drift checks (written to Audit sheet).
│   └── __init__.py
├── output/
│   ├── portfolio_tracker.xlsx  ← Generated Excel report (7 sheets).
│   ├── dashboard.html          ← Generated HTML dashboard (4 sections).
│   ├── latest_snapshot.json    ← Auto-saved after every hybrid/yf-only run.
│   └── run_YYYYMMDD_HHMM.log  ← Log file per run.
├── prompts/
│   ├── stage0_freshness_check.md  ← Paste into Claude: staleness triage (no web search).
│   ├── stage1_macro_regime.md     ← Paste into Claude: fetch macro data + generate MACRO_REGIME dict.
│   └── stage2_weekly_review.md    ← Paste into Claude: full weekly portfolio review (attach xlsx).
└── README.md                ← You are here.
```

---

## Excel Sheets

`output/portfolio_tracker.xlsx` contains 7 sheets, written in this order:

| Sheet | Source | Purpose |
|-------|--------|---------|
| 📊 Dashboard | transform + settings | Tier weights, P&L summary, macro regime, next review date |
| 📈 Holdings | extract + transform | All positions — price (blue/editable), shares, P&L, weight vs target |
| ⚖️ Rebalance Signals | transform | Satellite drift signals: TRIM/ADD/HOLD, shares to trade, est. proceeds |
| 🎯 Entry Signals | transform | P/E scoring (1–5), stop-loss flags, entry/exit signals per position |
| 📋 Audit | audit | Data freshness table + price drift vs snapshot (>10% flagged) |
| 👀 Watchlist | settings.WATCHLIST | All pending actions — action, target price, date, note; EXIT/TRIM highlighted red |
| 🔍 Screener | screener + yfinance | WATCHLIST tickers: P/E TTM, Fwd P/E, 5Y avg, premium, FCF yield, Quadrant D regime fit |

The **Screener** sheet is populated in hybrid and yf-only modes. In `--offline` mode it renders empty with a notice.

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
| Core | 68% | Passive index tracking | VOO, VXUS |
| Core-Bond | (part of Core) | Duration-managed bonds | SHY, VTIP, BND |
| Core-Plus | 11% | Income + growth ETFs | SPYD, ONEQ |
| Satellite | 21% | Active stock picks | RTX, GLDM, GOOG, NVDA, etc. |

### Satellite Targets

High-conviction positions get higher targets. The effective cap for breach detection is `max(target, 10%)` — so RTX at 18% target won't false-trigger the 10% hard cap.

### Rebalance Rules (settings.py)

- **3% drift threshold:** Position drifts >3% from target → signal generated (`REBALANCE_RULES['drift_threshold']`)
- **15% hard cap:** No single position >15% of satellite — raised from 10% to accommodate Tier-1 positions (GLDM, RTX, GOOG) (`REBALANCE_RULES['max_position_pct']`)
- **14-day review cycle:** Run the pipeline every 2 weeks minimum (`REBALANCE_RULES['review_cycle_days']`)
- **-15% stop-loss:** P&L below -15% from cost → exit signal (`SIGNAL_RULES['stop_loss_pct']`)

### Entry/Exit Scoring (1-5, lower = better)

| Score | Condition | Signal |
|-------|-----------|--------|
| 5 | P/E >30 AND >25% above 5Y avg | TRIM |
| 4 | P/E >30 OR >25% above 5Y avg | WATCH |
| 3 | Slightly above 5Y avg | HOLD |
| 2 | Near 5Y avg | HOLD |
| 1 | Below 5Y avg | ENTRY (good value) |

### Macro Regime (manual input)

The `MACRO_REGIME` dict in settings.py drives the dashboard. Update it at each 14-day review. The `REGIME_PLAYBOOK` maps each regime to bond duration targets and satellite overrides.

**Current regime (2026-07-08):** Stagflation-Lite / Hike-Risk, Geopolitical Escalation Re-Igniting | Quadrant D. Hormuz ceasefire (Islamabad MOU, Jun 17) declared "over" by Trump Jul 8 after mutual strikes. PCE 4.07% (May), CPI 4.2% (May), Brent $77.92 (+5.06%) on Hormuz tanker attacks. Defensive positioning maintained (SHY, VTIP, GLDM, RTX).

**Quadrant B watch:** Two conditions required to rotate — (1) Fed balance sheet > $7T (currently $6.736T, $264B away), (2) rate cut prob > 30% (currently ~15%). Rotation candidates: ISRG, APD, FCX, CCJ. Do not enter yet.

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

1. Add to `TICKER_TIERS` in settings.py (assign tier)
2. If satellite: add to `SATELLITE_TARGETS` with weight (0.07 default)
3. If satellite: add `PE_5Y_AVERAGES` entry
4. Add display name to `name_map` dict in load.py
5. Run pipeline to verify

### Adding a ticker to the Watchlist

1. Add entry to `WATCHLIST` in settings.py (fields: `ticker`, `action`, `note`, optional `target_price` / `trigger_date`)
2. Add a `WATCHLIST_REGIME_FIT` entry: `{'score': '✅|⚠️|❌', 'reason': '...'}`
3. If it has a 5Y P/E average available: add to `PE_5Y_AVERAGES`
4. Run pipeline — ticker will appear in the Watchlist and Screener sheets automatically

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

## Pending Actions (as of 2026-07-08)

See `WATCHLIST` in `config/settings.py` for the authoritative list. Key open items:

| Priority | Ticker | Action | Condition |
|----------|--------|--------|-----------|
| OPEN | BABA | Exit (stop-loss -15.8%) | Stop-loss triggered — sell and redeploy to GLDM or AON. |
| OPEN | XLE | Deferred entry | Thesis weakened at oil <$85; revisit if oil >$95. |
| OPEN | CAT | Trim 50% | P/E 41x (116% above 5Y avg). Proceeds → AON or MA. Re-entry at $580. |
| WATCH | MSFT | Entry trigger | Post-Apr 29 earnings: Azure ≥38% + stock >$380 + no lawsuit shock. |
| WATCH | Quadrant B | Pre-research ISRG, APD, FCX, CCJ | Trigger: Fed BS >$7T AND cut prob >30%. |

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