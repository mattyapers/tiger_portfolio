"""One-off valuation scan for current satellite holdings. Not part of the pipeline."""
import yfinance as yf
import json
import sys

TICKERS = ['GOOG','RTX','NVDA','TSM','AAPL','MA','CAT','KO','BABA','AON','COP','NTR','XLE','GLDM','SPYD','ONEQ','VOO','VXUS']

PE_5Y = {
    'GOOG': 25.0, 'RTX': 22.0, 'NVDA': 55.0, 'TSM': 22.0, 'AAPL': 28.0,
    'MA': 36.0, 'CAT': 19.0, 'KO': 24.0, 'BABA': 15.0, 'AON': 25.0,
    'COP': 13.0, 'NTR': 14.0,
}

rows = []
for t in TICKERS:
    try:
        info = yf.Ticker(t).info
        price = info.get('currentPrice') or info.get('regularMarketPrice')
        pe = info.get('trailingPE')
        fpe = info.get('forwardPE')
        fcf = info.get('freeCashflow')
        mcap = info.get('marketCap')
        fcf_yield = (fcf / mcap * 100) if (fcf and mcap) else None
        pe_5y = PE_5Y.get(t)
        premium = ((pe / pe_5y - 1) * 100) if (pe and pe_5y) else None
        rows.append({
            'symbol': t,
            'price': price,
            'pe_ttm': pe,
            'forward_pe': fpe,
            'pe_5y_avg': pe_5y,
            'pe_premium_pct': premium,
            'fcf_yield_pct': fcf_yield,
            'market_cap_b': (mcap / 1e9) if mcap else None,
        })
    except Exception as e:
        rows.append({'symbol': t, 'error': str(e)})

print(json.dumps(rows, indent=2, default=str))
