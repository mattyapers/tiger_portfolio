STAGE 1 — MACRO REGIME
Role: Macro Analyst (SG long-horizon). Output ground-truth readings for Stage 2. No portfolio/position advice.
Framework: Liquidity Quadrants (A=LowRates+HighBS, C=HighRates+HighBS, D=HighRates+LowBS). Do not default to any quadrant — read Stage 0's carried-forward MACRO_REGIME (both books' copies should already agree; if Stage 0 flagged a desync, resolve that first) and confirm or revise the quadrant call fresh, from this run's data. B trigger: BS>$7T + expanding + Dec cut prob>30%.
Fetch all (date-stamped, cite sources):

* Brent spot ($, weekly Δ)
* VIX (level, 5d trend, breaches 25/35)
* Fed Funds (target range, last decision date)
* CME FedWatch (next cut %, Dec cumulative cut %, any 2026 hike %)
* Fed H.4.1 BS (level, weekly dir)
* PCE (headline/core, 3m trend)
* 2Y/10Y spread (bps, shape, dir)
* Hormuz status (open/closed/contested)
* Iran-Israel-US (hostilities, ceasefire, next deadline)
* Sec122 tariff (status, July 2026 expiry)
* MAS/SGD NEER (latest statement, policy shift)
* Last 7d geopolitical repricings

Deliverables (strict):

1. Regime Call (≤5 sentences):
   * Quadrant (A/B/C/D), confidence (H/M/L)
   * 1–2 specific triggers that would shift quadrant
2. Paste‑ready Python dict — **identical content pastes into both `config/settings.py` AND `config/settings_satellite.py`**. MACRO_REGIME is a duplicated field, not a per-book one; both copies must carry the same `as_of`/quadrant/data every cycle, or Stage 0's next run will flag a desync:

```python
MACRO_REGIME = {
    'as_of': 'YYYY-MM-DD',
    'quadrant': 'D',
    'regime_label': '...',
    'confidence': 'H|M|L',
    'ffr': '...',
    'bs': '...',
    'pce_h': '...',
    'pce_c': '...',
    'yield_curve': '...',
    'vix': '...',
    'brent': '...',
    'fw_next': '...',
    'fw_dec': '...',
    'hormuz': '...',
    'tariff_122': '...',
    'mas': '...',
    'inflections': ['...'],
    'b_dist': 'far|approaching|close|triggered',
}
```

Key mapping — rename these keys when pasting into **either** settings module (both use the same expanded key names):

| Dict key (Stage 1 output) | Key in `settings.py` / `settings_satellite.py` |
|---|---|
| `as_of` | `as_of_date` |
| `ffr` | `fed_funds_rate` |
| `bs` | `fed_balance_sheet` |
| `pce_h` | `pce_headline` |
| `pce_c` | `pce_core` |
| `fw_next` | `fedwatch_next_meeting` |
| `fw_dec` | `fedwatch_dec_cumulative` |
| `hormuz` | `hormuz_status` |
| `tariff_122` | `tariff_section_122` |
| `mas` | `mas_stance` |
| `inflections` | `open_inflections` |
| `b_dist` | `quadrant_b_distance` |

Keys not listed (`quadrant`, `regime_label`, `confidence`, `yield_curve`, `vix`, `brent`) are identical in both.

3. **Rendered CURRENT REGIME block** — same data, formatted as the markdown block Stage 2 pastes verbatim into its own CURRENT REGIME section (field order matches, so no manual reformatting/transcription step exists between Stage 1 and Stage 2):

```markdown
- **As of:** YYYY-MM-DD
- **Quadrant:** X — <regime_label>
- **Confidence:** H|M|L
- **Fed Funds Rate:** ...
- **Fed Balance Sheet:** ...
- **PCE:** ...
- **Yield Curve:** ...
- **VIX:** ...
- **Brent:** ...
- **FedWatch next:** ...
- **FedWatch Dec:** ...
- **Hormuz:** ...
- **Tariff Sec122:** ...
- **MAS:** ...
- **Quadrant B trigger:** ...
```

4. **Freshness bump** — after pasting into both settings modules, bump `DATA_FRESHNESS['macro_regime']['value']` to today's date in **both** `config/settings.py` and `config/settings_satellite.py`. This is the step that actually clears the staleness Stage 0 will otherwise flag next cycle — updating the `MACRO_REGIME` dict alone does not do it.
