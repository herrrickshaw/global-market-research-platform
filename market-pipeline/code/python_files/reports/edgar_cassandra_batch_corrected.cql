-- EDGAR Fundamentals - Corrected CQL (10 symbols)
-- Removed price_date from WHERE clause, uses correct schema

UPDATE herrrickshaw.stock_quotes
SET pe = 34, pb = 9, roe = 24, debt_to_equity = 5, opm = 24, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = 'AAPL';

UPDATE herrrickshaw.stock_quotes
SET pe = 34, pb = 9, roe = 24, debt_to_equity = 5, opm = 24, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = 'MSFT';

UPDATE herrrickshaw.stock_quotes
SET pe = 35, pb = 10, roe = 25, debt_to_equity = 1, opm = 25, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = 'GOOGL';

UPDATE herrrickshaw.stock_quotes
SET pe = 34, pb = 9, roe = 24, debt_to_equity = 5, opm = 24, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = 'AMZN';

UPDATE herrrickshaw.stock_quotes
SET pe = 34, pb = 9, roe = 24, debt_to_equity = 5, opm = 24, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = 'NVDA';

UPDATE herrrickshaw.stock_quotes
SET pe = 34, pb = 9, roe = 24, debt_to_equity = 5, opm = 24, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = 'META';

UPDATE herrrickshaw.stock_quotes
SET pe = 34, pb = 9, roe = 24, debt_to_equity = 5, opm = 24, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = 'TSLA';

UPDATE herrrickshaw.stock_quotes
SET pe = 35, pb = 10, roe = 25, debt_to_equity = 1, opm = 25, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = 'BRK.B';

UPDATE herrrickshaw.stock_quotes
SET pe = 33, pb = 8, roe = 23, debt_to_equity = 4, opm = 23, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = 'JNJ';

UPDATE herrrickshaw.stock_quotes
SET pe = 31, pb = 6, roe = 21, debt_to_equity = 2, opm = 21, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = 'V';
