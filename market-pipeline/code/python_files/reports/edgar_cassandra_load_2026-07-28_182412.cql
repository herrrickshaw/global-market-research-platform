-- EDGAR Fundamentals Bulk Load - Auto-generated
-- Generated: 2026-07-28 18:24:12.453959
-- Records: 9
-- Run: cqlsh -f /Users/umashankar/market-pipeline/code/python_files/reports/edgar_cassandra_load_2026-07-28_182412.cql

UPDATE herrrickshaw.stock_quotes
SET pe = 32.5, pb = 52.1, roe = 89.5,
    debt_to_equity = 1.79, opm = 32.1
WHERE market = 'us' AND yf_ticker = 'AAPL'
  AND price_date = '2026-07-28';
UPDATE herrrickshaw.stock_quotes
SET pe = 42.3, pb = 15.8, roe = 43.2,
    debt_to_equity = 0.65, opm = 44.2
WHERE market = 'us' AND yf_ticker = 'MSFT'
  AND price_date = '2026-07-28';
UPDATE herrrickshaw.stock_quotes
SET pe = 25.1, pb = 7.9, roe = 20.1,
    debt_to_equity = 0.05, opm = 27.1
WHERE market = 'us' AND yf_ticker = 'GOOGL'
  AND price_date = '2026-07-28';
UPDATE herrrickshaw.stock_quotes
SET pe = 68.2, pb = 15.2, roe = 18.5,
    debt_to_equity = 1.23, opm = 8.1
WHERE market = 'us' AND yf_ticker = 'AMZN'
  AND price_date = '2026-07-28';
UPDATE herrrickshaw.stock_quotes
SET pe = 58.9, pb = 89.5, roe = 124.5,
    debt_to_equity = 0.42, opm = 62.1
WHERE market = 'us' AND yf_ticker = 'NVDA'
  AND price_date = '2026-07-28';
UPDATE herrrickshaw.stock_quotes
SET pe = 24.3, pb = 8.1, roe = 35.2,
    debt_to_equity = 0.0, opm = 38.1
WHERE market = 'us' AND yf_ticker = 'META'
  AND price_date = '2026-07-28';
UPDATE herrrickshaw.stock_quotes
SET pe = 71.2, pb = 42.3, roe = 55.8,
    debt_to_equity = 0.13, opm = 15.1
WHERE market = 'us' AND yf_ticker = 'TSLA'
  AND price_date = '2026-07-28';
UPDATE herrrickshaw.stock_quotes
SET pe = 24.5, pb = 8.2, roe = 45.2,
    debt_to_equity = 0.32, opm = 27.1
WHERE market = 'us' AND yf_ticker = 'JNJ'
  AND price_date = '2026-07-28';
UPDATE herrrickshaw.stock_quotes
SET pe = 45.2, pb = 12.5, roe = 32.1,
    debt_to_equity = 0.0, opm = 23.1
WHERE market = 'us' AND yf_ticker = 'NFLX'
  AND price_date = '2026-07-28';
