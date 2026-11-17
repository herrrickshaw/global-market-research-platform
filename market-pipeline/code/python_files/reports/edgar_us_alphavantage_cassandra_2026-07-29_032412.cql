-- US Fundamentals (AlphaVantage)
-- Extracted: 2026-07-29 03:24:12.017343
-- Source: alphavantage.co

UPDATE herrrickshaw.stock_quotes
SET pe = 40.79, pb = 45.93, roe = 1.415, debt_to_equity = 0,
    opm = 0.323, market_cap = 4948317176000.0, dividend_yield = 0.0031, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = 'AAPL';
UPDATE herrrickshaw.stock_quotes
SET pe = 15.25, pb = 2.656, roe = 0.178, debt_to_equity = 0,
    opm = 0.504, market_cap = 946850890000.0, dividend_yield = 0.017, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = 'JPM';
UPDATE herrrickshaw.stock_quotes
SET pe = 42.55, pb = 34.19, roe = 1.075, debt_to_equity = 0,
    opm = 0.494, market_cap = 1057489355000.0, dividend_yield = 0.0053, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = 'LLY';
UPDATE herrrickshaw.stock_quotes
SET pe = 17.92, pb = 8.44, roe = 0.515, debt_to_equity = 0,
    opm = 0.168, market_cap = 190953128000.0, dividend_yield = 0.0421, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = 'PEP';
