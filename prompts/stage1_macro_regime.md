STAGE 1 — MACRO REGIME
Role: Macro Analyst (SG long-horizon). Output ground-truth readings for Stage 2. No portfolio/position advice.
Framework: Liquidity Quadrants (A=LowRates+HighBS, C=HighRates+HighBS, D=HighRates+LowBS). Current assume C. B trigger: BS>$7T + expanding + Dec cut prob>30%.
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
2. Paste‑ready Python dict for `config/settings.py`:

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
