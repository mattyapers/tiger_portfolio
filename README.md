# Tiger Portfolio Tracker

A rules-based portfolio management pipeline for a Singapore-based investor running a Core (68%) / Core-Plus (11%) / Satellite (21%) allocation with a 30-year, 8% CAGR target. Generates both an interactive Excel report and a self-contained HTML dashboard.

**Author:** Matthew  
**Last Updated:** 2026-07-11  
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
  ├─ STAGE 3: load.py ───── write Excel (formulas, not hardcodes)
  │                       └── 4 sheets: Dashboard, Holdings,
  │                           Rebalance Signals, Entry Signals
  │
  └─ STAGE 3b: dashboard.py ─ fetch technical data (RSI, MAs, 52W range)
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
│   ├── load.py              ← Stage 3: Write Excel workbook.
│   ├── dashboard.py         ← Stage 3b: Generate HTML portfolio dashboard.
│   ├── audit.py             ← Data freshness checks.
│   └── __init__.py
├── output/
│   ├── portfolio_tracker.xlsx  ← Generated Excel report (4 sheets).
│   ├── dashboard.html          ← Generated HTML dashboard (4 sections).
│   ├── latest_snapshot.json    ← Auto-saved after every hybrid/yf-only run.
│   └── run_YYYYMMDD_HHMM.log  ← Log file per run.
└── README.md                ← You are here.
```

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
- Self-contained (73KB) — works offline after initial generation
- No external dependencies (uses Chart.js from free CDN)
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

- **3% drift threshold:** Position drifts >3% from target → signal generated
- **10% hard cap:** No single position >10% of satellite (unless target is higher)
- **14-day review cycle:** Run the pipeline every 2 weeks minimum
- **-15% stop-loss:** P&L below -15% from cost → exit signal

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

**Current regime (2026-04-18):** Stagflation-Lite + Ceasefire Transition | Quadrant D. Iran ceasefire announced Apr 8; expires Apr 21. Oil $102→$88, VIX 31→18. Defensive positioning (SHY, VTIP, GLDM, RTX) maintained until ceasefire outcome confirmed.

**Quadrant B watch:** Two conditions required to rotate — (1) Fed balance sheet > $7T upward, (2) rate cut prob > 30%. Condition 2 is close if oil normalizes and PCE falls toward 2.5%. Rotation candidates: ISRG, APD, FCX, CCJ. Do not enter yet.

---

## Common Workflows

### After executing a trade

1. Run `python main.py` (hybrid mode auto-pulls new positions from Tiger)
2. Check output Excel — verify new shares and signals
3. Snapshot auto-saves for future offline use

### 14-day review cycle

1. Run `python main.py`
2. Review Dashboard sheet: tier drift, macro regime
3. Review Rebalance Signals: any BREACH/TRIM/ADD?
4. Review Entry Signals: any score 1 (entry) or score 5 (trim)?
5. Update `MACRO_REGIME` in settings.py if conditions changed
6. Check `WATCHLIST` in settings.py for pending actions (exits, deferrals, triggers)
7. Log decisions in Notion checklist

### Adding a new ticker

1. Add to `TICKER_TIERS` in settings.py (assign tier)
2. If satellite: add to `SATELLITE_TARGETS` with weight (0.07 default)
3. If satellite: add `PE_5Y_AVERAGES` entry
4. Add display name to `name_map` dict in load.py
5. Run pipeline to verify

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

## Pending Actions (as of 2026-04-18)

| Priority | Ticker | Action | Condition |
|----------|--------|--------|-----------|
| URGENT | BABA | Exit (stop-loss -15.8%) | Execute immediately. Redeploy to GLDM or AON. |
| URGENT | XLE | Defer May tranche buy | Wait for Apr 21 ceasefire outcome. Buy if oil >$95, skip if oil <$85. |
| MONITOR | CAT | Trim 50% | P/E 41x (116% above 5Y avg). Proceeds → AON or MA. |
| PLAN | May tranche | Revise from SPYD+ONEQ+XLE+KO → SPYD+ONEQ+GLDM+AON | KO already overweight; XLE deferred. |
| WATCH | Quadrant B | Pre-research ISRG, APD, FCX, CCJ | Do not enter. Trigger: Fed BS >$7T AND cut prob >30%. |

## Future Roadmap

- [x] HTML dashboard with 4 integrated sections (Portfolio Overview, Stock Cards, Macro Monitor, Technical)
- [ ] Deploy to Synology NAS for automated daily runs
- [ ] Add correlation matrix sheet to Excel output
- [ ] Bond duration calculator sheet
- [ ] Extend technical indicators (Bollinger Bands, MACD, volume analysis)
- [ ] Add portfolio performance charts (daily/weekly/monthly returns)
- [ ] Automated Notion updates via MCP after each pipeline run