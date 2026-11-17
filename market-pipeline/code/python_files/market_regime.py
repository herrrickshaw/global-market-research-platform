"""Point-in-time market trend/vol regime per market, for gating scanner output.

Backed by the 2026-07 10-year Darvas replay (price_prediction_backtest repo,
docs/HISTORICAL_REPLAY.md): breakout-buys earn excess only/mostly in BULL
regimes (bear-regime breakouts are dead in US/JP/IN and negative in US), so
the daily scanner demotes BUY -> WATCH when a market's trend regime is 'bear'.

Index = trimmed mean (drop best+worst daily) of a fixed top-20 blue-chip
basket per market — the replay showed full-universe breadth medians are
structurally bearish in IN/KR/CN and mislabel entire decades. Trend label:
basket index vs its EMA100 and the EMA's 5-day slope. Vol label: trailing
252-day percentile of rolling 21-day vol.

Results are cached one day in data/regime_cache.json; failures degrade to
{'trend': 'unknown'} which applies no gate.
"""
from __future__ import annotations

import json
import os
from datetime import date

import numpy as np
import pandas as pd

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'reports', 'regime_cache.json')

# Top-20 by median dollar volume with >=95% coverage in the 10y panels
# (Europe hand-picked large caps — its deep panel is unavailable).
BASKETS: dict[str, list[str]] = {
    'us': ['SPY', 'TSLA', 'QQQ', 'AMZN', 'NVDA', 'MSFT', 'META', 'AMD', 'GOOGL',
           'GOOG', 'NFLX', 'BABA', 'BAC', 'JPM', 'BA', 'V', 'MU', 'GLD', 'INTC', 'XOM'],
    'india': ['RELIANCE.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS', 'INFY.NS',
              'AXISBANK.NS', 'TCS.NS', 'BAJFINANCE.NS', 'MARUTI.NS', 'TATASTEEL.NS',
              'BHARTIARTL.NS', 'KOTAKBANK.NS', 'LT.NS', 'ITC.NS', 'INDUSINDBK.NS',
              'HINDUNILVR.NS', 'VEDL.NS', 'M&M.NS', 'HCLTECH.NS', 'ONGC.NS'],
    'japan': ['9984.T', '6920.T', '7974.T', '7203.T', '9983.T', '8035.T', '6758.T',
              '8306.T', '6861.T', '8316.T', '6098.T', '4063.T', '8411.T', '9432.T',
              '6954.T', '6501.T', '6857.T', '6981.T', '9433.T', '4502.T'],
    'korea': ['005930.KS', '000660.KS', '035420.KS', '006400.KS', '068270.KS',
              '051910.KS', '005380.KS', '035720.KS', '005490.KS', '009150.KS',
              '000270.KS', '066570.KS', '207940.KS', '105560.KS', '096770.KS',
              '012330.KS', '003670.KS', '034020.KS', '015760.KS', '028300.KQ'],
    'china': ['600519.SS', '300059.SZ', '601318.SS', '000858.SZ', '002594.SZ',
              '000063.SZ', '002475.SZ', '601012.SS', '600030.SS', '000725.SZ',
              '600036.SS', '600276.SS', '601899.SS', '002460.SZ', '002466.SZ',
              '002241.SZ', '002230.SZ', '300274.SZ', '000651.SZ', '000333.SZ'],
    'europe': ['ASML.AS', 'SAP.DE', 'MC.PA', 'TTE.PA', 'SIE.DE', 'NESN.SW',
               'NOVN.SW', 'ZURN.SW', 'SHEL.L', 'AZN.L', 'HSBA.L', 'BP.L',
               'SAN.PA', 'AIR.PA', 'ALV.DE', 'DTE.DE', 'IBE.MC', 'ENEL.MI',
               'NOVO-B.CO', 'OR.PA'],
}


def _compute(market: str) -> dict:
    import yfinance as yf

    tickers = BASKETS[market]
    px = yf.download(tickers, period='2y', interval='1d', auto_adjust=True,
                     progress=False)['Close']
    if isinstance(px, pd.Series):
        px = px.to_frame()
    ret = px.pct_change()
    ret = ret.mask(ret.abs() > 0.6)
    n = ret.notna().sum(axis=1)
    trimmed = (ret.sum(axis=1) - ret.max(axis=1) - ret.min(axis=1)) / (n - 2)
    idx_ret = trimmed.where(n > 4).dropna()
    idx = (1 + idx_ret).cumprod()
    ema = idx.ewm(span=100, min_periods=100).mean()
    if ema.dropna().empty:
        return {'trend': 'unknown', 'vol': 'unknown'}
    slope = ema.diff(5).iloc[-1]
    above = idx.iloc[-1] > ema.iloc[-1]
    trend = 'bull' if (above and slope > 0) else (
        'bear' if (not above and slope < 0) else 'chop')
    vol21 = idx_ret.rolling(21).std()
    window = vol21.dropna().iloc[-252:]
    pct = float((window <= window.iloc[-1]).mean()) if len(window) > 60 else np.nan
    vol = 'unknown' if np.isnan(pct) else (
        'LOW' if pct <= 1 / 3 else ('MID' if pct <= 2 / 3 else 'HIGH'))
    return {'trend': trend, 'vol': vol}


_ALIAS = {'in': 'india', 'us': 'us', 'eu': 'europe', 'jp': 'japan',
          'kr': 'korea', 'cn': 'china', 'nse': 'india'}


def get_regime(market: str) -> dict:
    """{'trend': bull|chop|bear|unknown, 'vol': LOW|MID|HIGH|unknown, 'asof': iso}"""
    market = _ALIAS.get(market.lower(), market.lower())
    if market not in BASKETS:
        return {'trend': 'unknown', 'vol': 'unknown', 'asof': str(date.today())}
    today = str(date.today())
    cache = {}
    try:
        with open(CACHE) as f:
            cache = json.load(f)
    except Exception:
        pass
    hit = cache.get(market)
    if hit and hit.get('asof') == today:
        return hit
    try:
        reg = _compute(market)
    except Exception:
        return hit or {'trend': 'unknown', 'vol': 'unknown', 'asof': today}
    reg['asof'] = today
    cache[market] = reg
    try:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, 'w') as f:
            json.dump(cache, f, indent=1)
    except Exception:
        pass
    return reg
