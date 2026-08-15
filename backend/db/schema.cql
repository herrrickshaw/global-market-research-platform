-- Bootstrap script for the herrrickshaw keyspace.
-- Run manually via:  cqlsh -f backend/db/schema.cql
--
-- NOT the source of truth: db/cassandra_client.py is.  connect() applies
-- _SCHEMA (the CREATE statements below) and then _MIGRATIONS (ALTER TABLE ADD,
-- each in its own try/except) on every startup.  This file is the flattened
-- equivalent for bootstrapping a *fresh* keyspace by hand — the migration
-- columns are folded into the CREATE below rather than appended as ALTERs.
--
-- Keep in sync when you add to either list in cassandra_client.py.  Note that
-- against an existing keyspace every CREATE here is IF NOT EXISTS and will
-- silently no-op, so new columns only reach an existing table via _MIGRATIONS.

CREATE KEYSPACE IF NOT EXISTS herrrickshaw
    WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE herrrickshaw;

-- ── instruments tables (seeded from CSV files) ────────────────────────────────

CREATE TABLE IF NOT EXISTS instruments (
    market      text,
    yf_ticker   text,
    symbol      text,
    name        text,
    name_lower  text,
    isin        text,
    exchange    text,
    country     text,
    PRIMARY KEY (market, yf_ticker)
) WITH CLUSTERING ORDER BY (yf_ticker ASC);

-- Lookup by raw exchange code / NSE symbol / US ticker
CREATE TABLE IF NOT EXISTS instruments_by_symbol (
    market    text,
    symbol    text,
    yf_ticker text,
    name      text,
    PRIMARY KEY (market, symbol)
) WITH CLUSTERING ORDER BY (symbol ASC);

-- Lookup by lowercase company name (supports prefix-range queries)
CREATE TABLE IF NOT EXISTS instruments_by_name (
    market     text,
    name_lower text,
    yf_ticker  text,
    name       text,
    PRIMARY KEY (market, name_lower)
) WITH CLUSTERING ORDER BY (name_lower ASC);

-- Lookup by ISIN (India: INE…, US: US…, etc.)
CREATE TABLE IF NOT EXISTS instruments_by_isin (
    isin      text PRIMARY KEY,
    market    text,
    yf_ticker text,
    symbol    text,
    name      text
);

-- ── live quote cache ──────────────────────────────────────────────────────────
-- Updated fire-and-forget after every /api/live/fetch call.
-- Signal values: BUY | SELL | HOLD
--   BUY  = RSI < 30  AND Close > EMA_50
--   SELL = RSI > 70  AND Close < EMA_50
--   HOLD = otherwise

-- Column order below matches the prepared INSERT in db/quote_updater.py.
CREATE TABLE IF NOT EXISTS stock_quotes (
    market         text,
    yf_ticker      text,
    fetched_at     timestamp,
    cmp            double,
    rsi            double,
    ema_20         double,
    ema_50         double,
    ema_200        double,
    rsi_signal     text,
    macd           double,
    macd_signal    double,
    pe             double,
    pb             double,
    roe            double,
    opm            double,
    market_cap     double,
    volume         bigint,
    volume_20d_avg bigint,
    volume_ratio   double,
    high_52w       double,
    low_52w        double,
    debt_to_equity double,
    beta           double,
    current_ratio  double,
    revenue_growth double,
    eps            double,
    dividend_yield double,
    ret_1d         double,
    ret_1w         double,
    ret_1m         double,
    ret_3m         double,
    ret_6m         double,
    ret_1y         double,
    sector         text,
    industry       text,
    bb_upper       double,
    bb_lower       double,
    bb_pct         double,
    atr_14         double,
    stoch_k        double,
    stoch_d        double,
    PRIMARY KEY (market, yf_ticker)
) WITH CLUSTERING ORDER BY (yf_ticker ASC);

-- ── append-only daily snapshot of stock_quotes ────────────────────────────────
-- stock_quotes is overwritten in place, so every derived value it carries is lost
-- on the next fetch.  This table keeps one complete row per instrument per day so
-- signals can be backtested against their real historical inputs.  Written by
-- quote_updater.snapshot_market() at the end of the nightly batch — NOT from
-- upsert_quotes(); see MIGRATION_stock_quotes_history.md for why.
-- Partition is (market, yf_ticker): ~250 rows/year, clustered newest-first.

CREATE TABLE IF NOT EXISTS stock_quotes_history (
    market          text,
    yf_ticker       text,
    snapshot_date   date,
    fetched_at      timestamp,
    cmp             double,
    rsi             double,
    ema_20          double,
    ema_50          double,
    ema_200         double,
    rsi_signal      text,
    macd            double,
    macd_signal     double,
    pe              double,
    pb              double,
    roe             double,
    opm             double,
    market_cap      double,
    volume          bigint,
    volume_20d_avg  bigint,
    volume_ratio    double,
    high_52w        double,
    low_52w         double,
    debt_to_equity  double,
    beta            double,
    current_ratio   double,
    revenue_growth  double,
    eps             double,
    dividend_yield  double,
    ret_1d          double,
    ret_1w          double,
    ret_1m          double,
    ret_3m          double,
    ret_6m          double,
    ret_1y          double,
    sector          text,
    industry        text,
    bb_upper        double,
    bb_lower        double,
    bb_pct          double,
    atr_14          double,
    stoch_k         double,
    stoch_d         double,
    PRIMARY KEY ((market, yf_ticker), snapshot_date)
) WITH CLUSTERING ORDER BY (snapshot_date DESC);

-- ── historical price cache (date-of-purchase lookups) ─────────────────────────
-- Populated on demand by quote_updater.cache_price_on_date(); sparse, not a
-- dense OHLCV panel.

CREATE TABLE IF NOT EXISTS price_history (
    yf_ticker   text,
    price_date  date,
    close_price double,
    PRIMARY KEY (yf_ticker, price_date)
) WITH CLUSTERING ORDER BY (price_date DESC);

-- ── seeding book-keeping ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS seed_status (
    market    text PRIMARY KEY,
    seeded_at timestamp,
    row_count int
);
