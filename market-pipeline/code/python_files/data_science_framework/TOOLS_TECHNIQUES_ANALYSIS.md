# Comprehensive Analysis: Tools & Techniques From 4 Foundational Books

**Purpose:** Master reference guide for selecting & applying data science techniques to multi-market investment analysis.

**Scope:** 4 books × 3 categories (understanding, execution, validation) × applications to your repos

---

## Table of Contents

1. [Book 1: Linoff (SQL/Excel)](#book-1-data-analysis-using-sql-and-excel)
2. [Book 2: McKinney (Python)](#book-2-python-for-data-analysis)
3. [Book 3: Han/Kamber/Pei (Mining)](#book-3-data-mining-concepts-and-techniques)
4. [Book 4: Knaflic (Storytelling)](#book-4-storytelling-with-data)
5. [Integration Matrix](#integration-matrix)
6. [Decision Trees: Which Tool When](#decision-trees-which-tool-when)
7. [Advanced Techniques](#advanced-techniques)
8. [Anti-Patterns: What NOT to Do](#anti-patterns-what-not-to-do)

---

## Book 1: Data Analysis Using SQL and Excel

**Author:** Gordon S. Linoff  
**Core Principle:** Data quality >> model sophistication  
**Your Application:** Cassandra/DuckDB pipelines, market data ingestion

### Core Techniques

#### 1.1 Data Profiling & Quality Assessment

**What It Is:**  
Systematic examination of data characteristics before analysis.

**Techniques:**
| Technique | SQL | Excel | Your Use Case |
|-----------|-----|-------|--------------|
| Cardinality Analysis | `SELECT COUNT(DISTINCT col) FROM table` | Pivot table | Find unique tickers per exchange |
| Missing Value Analysis | `SELECT COUNT(*) WHERE col IS NULL` | COUNTBLANK() | Track data completeness % |
| Data Type Validation | `CAST(col AS type)` with error tracking | Data → Text to Columns | Ensure dates, prices are correct types |
| Duplicate Detection | `SELECT * FROM table GROUP BY * HAVING COUNT(*)>1` | Remove Duplicates | Find duplicate trades, quotes |
| Outlier Profiling | `SELECT * WHERE col > mean + 3*std` | Conditional formatting | Spot data errors vs real extremes |

**Real Example from Your Repos:**
```sql
-- Profile NSE OHLCV data quality
SELECT 
  ticker,
  COUNT(*) as total_rows,
  COUNT(CASE WHEN close > 0 THEN 1 END) / COUNT(*) as completeness,
  COUNT(CASE WHEN volume > 0 THEN 1 END) as volume_records,
  MIN(date) as earliest_date,
  MAX(date) as latest_date
FROM stock_quotes
WHERE market = 'india'
GROUP BY ticker
ORDER BY completeness ASC;
```

**When to Use:**
- ✅ Before every pipeline run
- ✅ After data import from new source
- ✅ When results suddenly change (data quality investigation)

---

#### 1.2 Data Integration & Reconciliation

**What It Is:**  
Combining data from multiple sources while preserving data integrity.

**Techniques:**

| Problem | SQL Solution | Your Context |
|---------|-----|-------------|
| Duplicate sources (NSE vs yfinance) | `SELECT DISTINCT * UNION / EXCEPT` | Reconcile India tickers |
| Schema mismatch | `ALTER TABLE`, type coercion | Normalize date formats (ISO, Excel, Unix timestamp) |
| Foreign key violation | `LEFT JOIN` + identify unmatched | Match tickers to instruments table |
| Update conflicts | Timestamp-based merge | Latest quote wins; historical preserved |
| Aggregation mismatch | `GROUP BY`, `HAVING` | Sum daily volume to weekly; verify totals match |

**Real Example:**
```sql
-- Reconcile NSE (Cassandra) vs yfinance (DuckDB)
WITH cassandra_data AS (
  SELECT ticker, date, close, volume FROM herrrickshaw.stock_quotes WHERE market='india'
),
yfinance_data AS (
  SELECT ticker, date, close, volume FROM duckdb_yfinance.india_prices
)
SELECT 
  COALESCE(c.ticker, y.ticker) as ticker,
  COALESCE(c.date, y.date) as date,
  c.close as cassandra_close,
  y.close as yfinance_close,
  ABS(c.close - y.close) / c.close as price_variance_pct,
  CASE 
    WHEN c.close IS NULL THEN 'Missing in Cassandra'
    WHEN y.close IS NULL THEN 'Missing in yfinance'
    WHEN ABS(c.close - y.close) / c.close > 0.01 THEN 'Price mismatch >1%'
    ELSE 'OK'
  END as status
FROM cassandra_data c
FULL OUTER JOIN yfinance_data y 
  ON c.ticker = y.ticker AND c.date = y.date
WHERE CASE... != 'OK'
ORDER BY price_variance_pct DESC;
```

**When to Use:**
- ✅ Multi-source data systems (NSE + yfinance + BSE)
- ✅ Before aggregating data for backtest
- ✅ Detecting data pipeline breaks

---

#### 1.3 Pivot Tables & Aggregation

**What It Is:**  
Reshaping data to find patterns across dimensions (time, market, sector).

**Techniques:**

```sql
-- Pivot: How many stocks per exchange improved today?
SELECT 
  exchange,
  SUM(CASE WHEN change > 0 THEN 1 ELSE 0 END) as gainers,
  SUM(CASE WHEN change < 0 THEN 1 ELSE 0 END) as losers,
  SUM(CASE WHEN change = 0 THEN 1 ELSE 0 END) as unchanged
FROM market_quotes
WHERE date = CURRENT_DATE
GROUP BY exchange;

-- Aggregation: Average return by sector
SELECT 
  sector,
  COUNT(*) as num_stocks,
  AVG(return_1y) as avg_return,
  STDDEV(return_1y) as volatility,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY return_1y) as median
FROM stocks
GROUP BY sector
ORDER BY avg_return DESC;
```

**Real Use Cases from Your Repos:**
- Daily market summary (gainers/losers by market)
- Sector performance (used in `SectorBenchmarks.jsx`)
- Zone rules validation (how many stocks in each zone per market)
- Watchlist analytics (signal types distribution)

---

#### 1.4 SQL for Time Series Analysis

**What It Is:**  
Window functions, cumulative aggregates, period-over-period comparisons.

**Techniques:**

```sql
-- Cumulative return
SELECT 
  date,
  close,
  LAG(close) OVER (ORDER BY date) as prev_close,
  (close - LAG(close) OVER (ORDER BY date)) / LAG(close) OVER (ORDER BY date) as daily_return,
  EXP(SUM(LN(1 + daily_return)) OVER (ORDER BY date)) - 1 as cumulative_return
FROM price_history
ORDER BY date;

-- Moving averages
SELECT 
  date,
  close,
  AVG(close) OVER (ORDER BY date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) as sma_50,
  AVG(close) OVER (ORDER BY date ROWS BETWEEN 199 PRECEDING AND CURRENT ROW) as sma_200
FROM price_history
ORDER BY date;

-- Year-over-year comparison
SELECT 
  DATE_TRUNC('month', date) as month,
  EXTRACT(YEAR FROM date) as year,
  SUM(volume) as monthly_volume
FROM price_history
GROUP BY month, year
PIVOT TABLE ON year
-- Shows: Jan 2024 vol, Jan 2025 vol, etc.
```

**When to Use:**
- ✅ Performance benchmarking (YTD return, 1Y return)
- ✅ Trend detection (price above/below MA)
- ✅ Seasonal analysis (Oct effect, January effect)

---

### Key Takeaway from Linoff

**"Data quality is a feature, not a bug."**

Before building any model:
1. Profile the data (missing %, types, ranges)
2. Reconcile multi-source conflicts
3. Document assumptions (e.g., "raw-Close" vs "Adjusted-Close")
4. Set up monitoring (daily quality checks)

**Applied to Your System:**
```python
# From data_science_framework/core.py - DataQualityReport
report = pipeline.quality_log[-1]
if not report.is_valid():
    logger.error(f"Quality failed: {report}")
    # Don't proceed to trading
```

---

## Book 2: Python for Data Analysis

**Author:** Wes McKinney (creator of pandas)  
**Core Principle:** Time series wrangling is 80% of data science work  
**Your Application:** OHLCV processing, feature engineering, portfolio analytics

### Core Techniques

#### 2.1 Time Series Fundamentals

**What It Is:**  
Handling temporal data: indexing, resampling, frequency conversion.

**Techniques:**

```python
import pandas as pd
import numpy as np

# Convert string to datetime
prices = pd.read_csv('prices.csv')
prices['date'] = pd.to_datetime(prices['date'])
prices.set_index('date', inplace=True)

# Resampling: daily → weekly → monthly
weekly_ohlc = prices['close'].resample('W').ohlc()
monthly_returns = prices['close'].resample('M').last().pct_change()

# Fill missing data (gaps in trading)
# Forward fill: use previous close if trading halted
prices = prices.asfreq('D', method='ffill')
# Interpolate: smooth gaps
prices = prices.interpolate(method='linear')

# Shift & lag: create feature for momentum
prices['prev_close'] = prices['close'].shift(1)
prices['return_1d'] = prices['close'].pct_change()
prices['return_5d'] = prices['close'].pct_change(5)  # 5-day return
```

**Real Example from Your Repos:**

```python
# From your RSI calculation
def calculate_rsi(close_prices, period=14):
    delta = close_prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# Now: Add lag features for mean-reversion detection
prices['rsi'] = calculate_rsi(prices['close'])
prices['rsi_prev_1'] = prices['rsi'].shift(1)
prices['rsi_prev_5'] = prices['rsi'].shift(5)
# Pattern: RSI improved from 25 → 35 in 5 days = recovery signal
```

**When to Use:**
- ✅ Every time you load market data
- ✅ Creating lagged features for ML
- ✅ Converting between timeframes (minute → day → month)

---

#### 2.2 Groupby & Aggregation

**What It Is:**  
Split-apply-combine pattern for efficient data processing.

**Techniques:**

```python
# Group by sector, calculate stats
sector_stats = df.groupby('sector').agg({
    'return_1y': ['mean', 'std', 'min', 'max'],
    'volume': 'sum',
    'market_cap': 'mean'
}).round(4)

# Multiple aggregation functions at once
portfolio_summary = df.groupby(['ticker', 'date']).agg(
    open_price=('open', 'first'),
    close_price=('close', 'last'),
    high_price=('high', 'max'),
    low_price=('low', 'min'),
    total_volume=('volume', 'sum'),
    trade_count=('volume', 'count')
).reset_index()

# Transform: apply function within groups (normalize per sector)
df['return_vs_sector_mean'] = df.groupby('sector')['return_1y'].transform(
    lambda x: x - x.mean()
)

# Filter: stocks that underperformed their sector
underperformers = df[df['return_vs_sector_mean'] < -0.05]
```

**Real Example from Your Code:**

```python
# From daily_scanner.py - calculate Darvas per sector
darvas_by_sector = df.groupby('sector').apply(
    lambda group: pd.Series({
        'num_darvas_signals': (group['darvas_score'] >= 5).sum(),
        'avg_score': group['darvas_score'].mean(),
        'pct_in_box': (group['darvas_score'] >= 5).sum() / len(group)
    })
)
```

**When to Use:**
- ✅ Market summary statistics
- ✅ Per-market/sector analysis
- ✅ Normalizing metrics (e.g., return vs benchmark)

---

#### 2.3 Rolling Windows & Exponential Moving Averages

**What It Is:**  
Continuous calculations over sliding time windows.

**Techniques:**

```python
# Simple Moving Average (SMA)
prices['sma_20'] = prices['close'].rolling(20).mean()
prices['sma_50'] = prices['close'].rolling(20).mean()
prices['sma_200'] = prices['close'].rolling(200).mean()

# Exponential Moving Average (EMA) - recent values weighted more
prices['ema_12'] = prices['close'].ewm(span=12).mean()
prices['ema_26'] = prices['close'].ewm(span=26).mean()

# MACD: EMA crossover indicator
prices['macd'] = prices['ema_12'] - prices['ema_26']
prices['signal_line'] = prices['macd'].ewm(span=9).mean()
prices['macd_histogram'] = prices['macd'] - prices['signal_line']

# Bollinger Bands
prices['sma_20'] = prices['close'].rolling(20).mean()
prices['std_20'] = prices['close'].rolling(20).std()
prices['bb_upper'] = prices['sma_20'] + 2 * prices['std_20']
prices['bb_lower'] = prices['sma_20'] - 2 * prices['std_20']

# Volatility (rolling std)
prices['volatility_30d'] = prices['return'].rolling(30).std() * np.sqrt(252)

# Correlation with market
market_returns = load_nifty50_returns()
prices['correlation_market'] = prices['return'].rolling(60).corr(market_returns)
```

**Real Use from Your Repos:**
- `bulk_fetcher.py`: Calculates RSI-14 (rolling max/min)
- `daily_scanner.py`: Uses SMA-50, SMA-200 for Darvas
- `zone_rules.json`: EMA-based entry/exit

**Optimization Trick:**
```python
# Don't recalculate from scratch; update incrementally
# For new data point: only update last row
df.loc[df.index[-1], 'sma_20'] = df['close'].tail(20).mean()

# For 10,000 stocks × 2,500 days = 25M calculations
# Incremental update: 10,000 × 1 = 10K (1000x faster)
```

**When to Use:**
- ✅ Every technical indicator (RSI, MACD, Bollinger)
- ✅ Trend detection (price vs MA)
- ✅ Volatility estimates

---

#### 2.4 Missing Data Handling

**What It Is:**  
Strategies for gaps in time series data (trading halts, data errors, etc.).

**Techniques:**

```python
# Identify missing data
print(df.isnull().sum())  # Count missing per column
print(df.isnull().sum() / len(df))  # Percentage

# Forward fill: assume last trade holds (holiday gaps)
df = df.asfreq('D', method='ffill')

# Interpolate: smooth gaps (more realistic)
df['close'] = df['close'].interpolate(method='linear')

# Drop rows with >20% missing
df = df.dropna(thresh=0.8 * len(df.columns))

# Fill with mean/median (price columns: median, volume: mean)
df['close'] = df['close'].fillna(df['close'].median())
df['volume'] = df['volume'].fillna(df['volume'].mean())

# Sophisticated: use previous day's close + interpolate
df['close_filled'] = df['close'].fillna(method='ffill').interpolate()
```

**Decision Tree for Missing Data:**

```
Missing Data?
├─ Why missing?
│  ├─ Trading halt → use last valid close (ffill)
│  ├─ Data error → remove row
│  └─ Sparse asset → use mean
├─ How much missing?
│  ├─ <5% → interpolate
│  ├─ 5-20% → ffill
│  └─ >20% → drop column/row
└─ Time series or cross-section?
   ├─ Time series → ffill then interpolate
   └─ Cross-section → mean/median fill
```

**Real from Your Code:**
```python
# From bulk_fetcher.py
if df.isnull().sum().sum() > len(df) * 0.1:
    logger.warning(f"Data {ticker} has >10% missing, skipping")
    continue
```

**When to Use:**
- ✅ Before calculating indicators
- ✅ Data validation step
- ✅ Quality check report

---

#### 2.5 Reshaping & Pivoting

**What It Is:**  
Converting data between long (normalized) and wide (pivoted) formats.

**Techniques:**

```python
# Long format (database-friendly)
prices_long = pd.DataFrame({
    'ticker': ['RELIANCE', 'RELIANCE', 'INFY', 'INFY'],
    'date': ['2024-01-01', '2024-01-02', '2024-01-01', '2024-01-02'],
    'close': [2500, 2510, 2300, 2310]
})

# Wide format (analysis-friendly)
prices_wide = prices_long.pivot(index='date', columns='ticker', values='close')
#              INFY  RELIANCE
# 2024-01-01  2300      2500
# 2024-01-02  2310      2510

# Correlation matrix (only works with wide format)
correlation = prices_wide.corr()

# Stack/unstack: toggle between long/wide
prices_long = prices_wide.stack().reset_index()
prices_wide = prices_long.pivot_table(index='date', columns='ticker', values='close')

# Melt: unpivot (wide → long)
prices_long = prices_wide.reset_index().melt(id_vars='date', var_name='ticker', value_name='close')
```

**When to Use:**
- ✅ Correlation analysis (requires wide)
- ✅ Portfolio analysis (per-stock vs per-date)
- ✅ Visualization (wide format easier to plot)

---

### Key Takeaway from McKinney

**"Time series wrangling is 80% of the work. Master lags, rolling windows, and resampling."**

Applied to Your System:
```python
# From FeatureEngineering in framework
@staticmethod
def create_lag_features(series, lags=[1, 5, 20]):
    """Create lagged features for momentum detection."""
    result = pd.DataFrame()
    for lag in lags:
        result[f'lag_{lag}'] = series.shift(lag)
    return result

# Use:
features = FeatureEngineering.create_lag_features(df['close'], lags=[1,5,20])
# Now: close_lag1 = yesterday's close, etc.
```

---

## Book 3: Data Mining: Concepts and Techniques

**Authors:** Jiawei Han, Micheline Kamber, Jian Pei  
**Core Principle:** Automated pattern discovery; algorithms scale to big data  
**Your Application:** Stock clustering, anomaly detection, signal mining

### Core Techniques

#### 3.1 Classification Algorithms

**What It Is:**  
Predicting a target class (BUY/SELL/HOLD) from features.

**Algorithms:**

| Algorithm | Use Case | Pros | Cons | Your Application |
|-----------|----------|------|------|-----------------|
| **Decision Tree** | Simple rules | Interpretable, fast | Overfits easily | Zone rules generation |
| **Naive Bayes** | Quick baseline | Fast, handles missing | Assumes independence | Market regime classifier |
| **Logistic Regression** | Linear separation | Simple, fast, explainable | Linear only | Win rate predictor |
| **Random Forest** | Complex patterns | Robust, feature importance | Black box | Sector classification |
| **SVM** | High-dimensional data | Good generalization | Slow, parameter tuning | Signal quality classifier |

**Real Example: Decision Tree for Trading Signals**

```python
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split

# Prepare data
X = df[['rsi', 'price_above_sma50', 'volume_surge']]  # Features
y = df['actual_signal']  # Target: 'BUY' or 'SELL'

# Train-test split (80-20)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
# Note: shuffle=False for time series (don't mix past & future)

# Train tree
tree = DecisionTreeClassifier(max_depth=5)  # Limit depth to prevent overfitting
tree.fit(X_train, y_train)

# Predict
y_pred = tree.predict(X_test)

# Evaluate
from sklearn.metrics import confusion_matrix, classification_report
print(classification_report(y_test, y_pred))
# Output: precision, recall, F1-score per class

# Interpret
from sklearn import tree as tree_module
tree_module.plot_tree(tree)  # Visualize the decision rules
```

**Applied to Your System:**

```python
# From daily_scanner.py
# Before: hardcoded if (rsi<30 and price>ma50): buy
# After: train tree on historical data

# Historical labels: did this actually work?
df['actually_gained_5d'] = df['close'].shift(-5) > df['close']  # 5-day forward return

# Train classifier
features = df[['rsi', 'macd', 'volume_ratio', 'price_vs_ma50']]
labels = df['actually_gained_5d']

clf = DecisionTreeClassifier(max_depth=4)
clf.fit(features, labels)

# Now: signal = tree.predict([rsi=25, macd=-10, ...])
# More robust than hardcoded thresholds
```

**When to Use:**
- ✅ First step in any classification problem
- ✅ Understanding what matters (feature importance)
- ✅ Comparing to other algorithms

---

#### 3.2 Clustering Algorithms

**What It Is:**  
Grouping similar items without labels (unsupervised learning).

**Algorithms:**

| Algorithm | Clusters | Distance Metric | Pros | Cons |
|-----------|----------|-----------------|------|------|
| **K-Means** | Spherical | Euclidean | Fast, scalable | Must specify K, outlier-sensitive |
| **Hierarchical** | Dendrogram | Any | Dendrograms intuitive | Slow on large data |
| **DBSCAN** | Arbitrary shape | Any | Finds arbitrary clusters, noise | Parameter tuning hard |
| **GMM** | Gaussian mixture | Probability | Soft assignments | Assumes Gaussian |

**Real Example: Stock Clustering**

```python
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Prepare features
features = df[['pe_ratio', 'pb_ratio', 'dividend_yield', 'momentum_1y']]

# Standardize (K-Means is distance-sensitive)
scaler = StandardScaler()
features_scaled = scaler.fit_transform(features)

# Elbow method: find optimal K
inertias = []
for k in range(1, 11):
    kmeans = KMeans(n_clusters=k, random_state=42)
    kmeans.fit(features_scaled)
    inertias.append(kmeans.inertia_)

# Plot inertia vs K; pick "elbow" point
import matplotlib.pyplot as plt
plt.plot(range(1, 11), inertias, 'bo-')
plt.xlabel('K (number of clusters)')
plt.ylabel('Inertia')
plt.show()  # Usually K=3-5 for stock data

# Fit final model
kmeans = KMeans(n_clusters=4, random_state=42)
df['cluster'] = kmeans.fit_predict(features_scaled)

# Interpret
cluster_centers = scaler.inverse_transform(kmeans.cluster_centers_)
print(pd.DataFrame(cluster_centers, columns=features.columns))
# Output: 
#   pe_ratio  pb_ratio  div_yield  momentum_1y
# 0    15.2      1.8      2.1%      +12%
# 1    25.3      3.2      0.8%      +35%  (growth stocks)
# 2     8.5      0.9      4.2%      -5%   (value trap?)
# 3    18.1      2.1      1.5%      +18%
```

**Applied to Your System:**

```python
# Stock clustering for portfolio construction
# Cluster 0: Value (low PE, high dividend)
# Cluster 1: Growth (high momentum, low dividend)
# Cluster 2: Defensive (stable, low volatility)

portfolio = []
for cluster_id in range(4):
    cluster_stocks = df[df['cluster'] == cluster_id].nlargest(5, 'market_cap')
    portfolio.extend(cluster_stocks['ticker'].tolist())

# Result: diversified portfolio across 4 distinct clusters
```

**When to Use:**
- ✅ Portfolio construction (pick from each cluster)
- ✅ Understanding market structure
- ✅ Anomaly detection (outlier clusters)

---

#### 3.3 Outlier Detection

**What It Is:**  
Finding unusual observations (data errors vs real opportunities).

**Algorithms:**

```python
# 1. Z-Score: univariate, assumes normal distribution
from scipy import stats

z_scores = np.abs(stats.zscore(df['return']))
outliers = df[z_scores > 3]  # 3-sigma rule
# Better for: detecting data errors, extreme moves

# 2. IQR (Interquartile Range): robust, non-parametric
Q1 = df['return'].quantile(0.25)
Q3 = df['return'].quantile(0.75)
IQR = Q3 - Q1
outliers = df[(df['return'] < Q1 - 1.5*IQR) | (df['return'] > Q3 + 1.5*IQR)]
# Better for: real market anomalies (doesn't assume normal)

# 3. Mahalanobis Distance: multivariate (accounts for correlation)
from scipy.spatial.distance import mahalanobis

features = df[['return', 'volume', 'volatility']].values
cov_matrix = np.cov(features.T)
cov_inv = np.linalg.inv(cov_matrix)
mean = features.mean(axis=0)

distances = []
for point in features:
    d = mahalanobis(point, mean, cov_inv)
    distances.append(d)

outliers = df[np.array(distances) > np.percentile(distances, 95)]

# 4. Isolation Forest: scalable, handles high-dimensional data
from sklearn.ensemble import IsolationForest

clf = IsolationForest(contamination=0.05)  # Expect 5% outliers
outliers_flag = clf.fit_predict(features)
outliers = df[outliers_flag == -1]
```

**Decision Tree: When to Use Which Outlier Detector**

```
Outlier Detection?
├─ Single variable (e.g., price change)?
│  └─ Z-score (normal assumption) or IQR (robust)
├─ Multiple variables (e.g., price + volume)?
│  └─ Mahalanobis (accounts for correlation)
├─ High-dimensional (10+ variables)?
│  └─ Isolation Forest (scalable)
└─ What to do with outliers?
   ├─ Data error? → Remove
   ├─ Real signal? → Trade it
   └─ Uncertain? → Flag for review
```

**Real from Your Repos:**

```python
# From pe_anomaly_backtest.md
# India sector PE is mean-reverting
# Outlier = stock significantly cheaper than sector

sector_pe_median = df.groupby('sector')['pe_ratio'].median()
df['pe_vs_sector'] = df['pe_ratio'] - df['sector'].map(sector_pe_median)

outliers = df[np.abs(df['pe_vs_sector']) > df['pe_vs_sector'].std() * 2]
# Find stocks trading at 2-sigma discount to sector = reentry candidates
```

**When to Use:**
- ✅ Anomaly detection in derivatives (parity deviation)
- ✅ Data quality checks (remove errors)
- ✅ Finding mispricings (trading opportunities)

---

#### 3.4 Frequent Pattern Mining

**What It Is:**  
Finding common co-occurrences in data (market structure).

**Algorithms:**

```python
# Apriori: find itemsets that appear frequently

# Example: What signal combinations appear most?
# Transform data to binary: RSI>70? Volume>avg? Price>MA50?

from mlxtend.frequent_itemsets import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder

# Create binary features
signals = []
for idx, row in df.iterrows():
    itemset = []
    if row['rsi'] > 70: itemset.append('RSI_overbought')
    if row['price'] > row['sma_50']: itemset.append('Price_above_MA50')
    if row['volume'] > row['avg_volume']: itemset.append('Volume_surge')
    if row['macd'] > row['signal_line']: itemset.append('MACD_positive')
    signals.append(itemset)

# Convert to one-hot encoding
te = TransactionEncoder()
te_ary = te.fit(signals).transform(signals)
df_encoded = pd.DataFrame(te_ary, columns=te.columns_)

# Find frequent itemsets (appear in >5% of days)
frequent_itemsets = apriori(df_encoded, min_support=0.05, use_colnames=True)
print(frequent_itemsets)
# Output:
#                              support
# RSI_overbought                 0.08
# Price_above_MA50               0.45
# Volume_surge                   0.12
# RSI_overbought & Price_above_MA50  0.07  ← Interesting!

# Association rules: what predicts what?
rules = association_rules(frequent_itemsets, metric='lift', min_threshold=1.0)
# Lift > 1 = correlated; Lift < 1 = negatively correlated
print(rules[['antecedants', 'consequents', 'support', 'confidence', 'lift']])
```

**Applied to Your System:**

```python
# Signal combination analysis
# Q: Which signal combinations actually work?

# Train on 3-year history
rules = mining.find_frequent_patterns(df)

# Evaluate: of trades following pattern X, what % were profitable?
for rule in rules:
    pattern = rule['antecedents']  # e.g., {RSI<30, Volume>2x avg}
    consequence = rule['consequent']  # e.g., 5-day gain
    
    # Backtests
    trades = df[apply_pattern(df, pattern)]
    win_rate = (trades['return_5d'] > 0).mean()
    
    if win_rate > 0.55:
        print(f"Pattern {pattern} → {win_rate:.1%} win rate ✓")
```

**When to Use:**
- ✅ Understanding market structure (what signals coexist)
- ✅ Finding validated signal combinations
- ✅ Reducing false signals (require multiple confirmations)

---

#### 3.5 Temporal Pattern Mining

**What It Is:**  
Finding patterns that evolve over time.

**Techniques:**

```python
# Sequence mining: find common trading patterns

# Pattern: What happens after large gap up?
pattern = df[df['gap'] > 2.0]  # Gap > 2%

# Next 5 days: tendency to revert?
df['5d_after_gap'] = df[df['gap'] > 2.0]['close'].shift(-5) / df['close'] - 1

reversion_rate = (df['5d_after_gap'] < 0).mean()  # Did it revert?
print(f"After gap >2%, reverted {reversion_rate:.1%} of time")

# Seasonal patterns
df['month'] = df['date'].dt.month
df['quarter'] = df['date'].dt.quarter

seasonal_return = df.groupby('month')['return'].mean()
print(seasonal_return)
# Output:
# 1    +0.8%
# 2    -0.2%
# 3    +0.5%
# ... October effect?

# Day-of-week effects
df['dow'] = df['date'].dt.dayofweek
dow_returns = df.groupby('dow')['return'].mean()
# Monday effect? Friday rally?
```

**Applied to Your System:**

```python
# From your zone_rules.json
# Q: Do certain zones work better in certain seasons?

zone_seasonal = df.groupby(['zone_id', 'quarter']).agg({
    'return_after_entry': 'mean',
    'signal_count': 'count'
}).reset_index()

# Find: Zone 2 works best in Q1, Zone 4 in Q4
```

**When to Use:**
- ✅ Seasonal strategy adjustment
- ✅ Understanding market anomalies
- ✅ Calendar-based trading (e.g., Halloween indicator)

---

### Key Takeaway from Han/Kamber/Pei

**"Not all patterns are useful. Test for statistical significance before acting."**

Applied to Your System:
```python
# From PatternDiscovery in framework
# Don't just find patterns; validate them

pattern = frequent_itemsets[...]
# Test: Is this pattern significantly correlated with returns?
test_result = StatisticalTesting.test_correlation(pattern_signal, returns)
if test_result['p_value'] < 0.05:
    print("Significant pattern found!")
else:
    print("Random noise, skip")
```

---

## Book 4: Storytelling with Data

**Author:** Cole Nussbaumer Knaflic  
**Core Principle:** Data without narrative is ignored; narrative without data is wrong  
**Your Application:** Daily reports, backtest summaries, signal narratives

### Core Techniques

#### 4.1 The Data-Ink Ratio

**What It Is:**  
Maximize the proportion of ink (pixels) used for data vs decoration. (The term
originates with Edward Tufte, *The Visual Display of Quantitative Information*,
1983; Knaflic applies the same decluttering principle.)

**Bad Practice (High Ink Waste):**
```
═══════════════════════════════════════
║ DAILY MARKET REPORT - SEPTEMBER 2024 ║  ← Decorative
║ ═══════════════════════════════════  ║
║                                       ║
║ Market Performance                    ║  ← Title only
║ ───────────────────────────────────  ║
║ 📈 NSE: +1.2% (Gainers: 1,200)      ║  ← Emoji waste
║ 📈 BSE: +0.8% (Gainers: 400)        ║
║ 📈 Nifty 50: +1.5%                  ║
║ 📉 Nifty 100: -0.3%                 ║
║                                       ║
═══════════════════════════════════════
```

**Good Practice (High Data-Ink):**
```
NSE:     +1.2% | Gainers: 1,200 (55%)
BSE:     +0.8% | Gainers: 400 (48%)
Nifty50: +1.5% ↑
```

**Rule of Thumb:**
- Remove all decorative elements (gradients, 3D, shadows)
- Use color only to encode data (not decoration)
- Label directly on chart (avoid legends where possible)

**Applied to Your Reports:**

```python
# Bad: Generic summary
print(f"Strategy returned {return_pct:.2%}")

# Good: Narrative with context
print(f"""
Strategy Performance: +{return_pct:.2%} (vs benchmark +{bench_return:.2%}, outperformed by {outperformance:.2%})
Risk Profile: Volatility {volatility:.1%} (vs market {market_vol:.1%})
Consistency: Win rate {win_rate:.1%} (55% is breakeven in a 50:50 market)
Risk-Adjusted: Sharpe {sharpe:.2f} (>1.0 is strong)
""")
```

---

#### 4.2 Narrative Structure

**What It Is:**  
Guiding audience from data → insight → action via 3-act structure.

**Structure:**

```
ACT 1: THE SITUATION
├─ Current state: "NSE gained 1.2% today"
├─ Context: "Up 5.2% YTD vs benchmark +4.1%"
└─ Curiosity: "What drove the outperformance?"

ACT 2: THE COMPLICATION
├─ Darvas signals: 120 stocks (up from 80 yesterday)
├─ Regime change: Market shifted from mean-reverting to trending
└─ Risk: High-beta stocks (IT, pharma) led gains

ACT 3: THE RESOLUTION
├─ Insight: "Regime shift favors momentum strategies"
├─ Action: "Increase Darvas signal weight from 40% to 60%"
└─ CTA: "Review performance daily; revert if regime flips"
```

**Applied to Backtest Report:**

```python
def generate_backtest_narrative(metrics, comparison_benchmark):
    """Transform metrics into actionable narrative."""
    
    return f"""
SITUATION:
Your strategy returned {metrics['return']:.1%} annually while the benchmark returned {comparison_benchmark['return']:.1%}.

COMPLICATION:
But this outperformance came at a cost:
• Your strategy's volatility was {metrics['volatility']:.1%} vs benchmark {comparison_benchmark['volatility']:.1%}
• Maximum drawdown was {metrics['max_drawdown']:.1%} (you lost this much at worst point)
• Only {metrics['win_rate']:.0%} of your trades were profitable (barely above 50-50)

RESOLUTION:
The Sharpe ratio ({metrics['sharpe']:.2f}) shows risk-adjusted returns are decent, BUT:
1. Volatility is {(metrics['volatility']/comparison_benchmark['volatility']):.1f}x higher — you took on significant risk
2. Drawdown recovery took {metrics['dd_recovery_days']} days — this could have bankrupted leveraged positions

RECOMMENDATION:
✓ Keep the strategy if you can tolerate {metrics['max_drawdown']:.1%} drawdown
✗ Add stop-losses if you can't tolerate this volatility
  Consider: Regime detection (only trade when market favors this strategy)
"""
```

**When to Use:**
- ✅ Every backtest report
- ✅ Daily market summaries
- ✅ Presenting findings to stakeholders

---

#### 4.3 Choosing the Right Chart

**What It Is:**  
Matching chart type to data characteristics and question being asked.

**Decision Tree:**

```
What question am I answering?

COMPARISON (Is A bigger than B?)
├─ Categorical (sector comparison)
│  └─ Bar chart (horizontal bars for long labels)
├─ Ranking (best 10 stocks)
│  └─ Sorted bar chart
└─ Multiple series (3+ groups)
   └─ Grouped bars or small multiples

TIME SERIES (How does X change over time?)
├─ Single line → Line chart
├─ Multiple lines (3-5) → Multi-line chart
├─ Many lines (10+) → Faceted small multiples (one panel per line)
└─ Overlapping areas → Stacked area (use sparingly)

DISTRIBUTION (How is data spread?)
├─ Histogram (bins)
├─ Density curve (smooth)
└─ Box plot (quartiles + outliers)

CORRELATION (Relationship between X and Y?)
├─ Scatter plot
├─ With trend line (yes, add it)
└─ 3 variables → Bubble chart (but avoid; use small multiples instead)

COMPOSITION (Parts of a whole?)
├─ <3 parts → Pie chart (avoid; bar chart is clearer)
├─ 3-5 parts → Stacked bar
└─ Many parts → Don't use pie; use table or sorted bar
```

**Applied to Your Backtest Report:**

```python
import matplotlib.pyplot as plt

fig, axes = plt.subplots(2, 2, figsize=(12, 8))

# 1. Time series: Cumulative return
ax = axes[0, 0]
cumulative_return = (1 + returns).cumprod() - 1
ax.plot(cumulative_return.index, cumulative_return * 100, linewidth=2, color='#1f77b4')
ax.set_ylabel('Cumulative Return (%)')
ax.grid(True, alpha=0.3)
ax.set_title('Strategy vs Benchmark Cumulative Return')

# 2. Distribution: Returns histogram
ax = axes[0, 1]
ax.hist(returns, bins=50, alpha=0.7, color='#2ca02c', edgecolor='black')
ax.axvline(returns.mean(), color='red', linestyle='--', label=f'Mean: {returns.mean():.2%}')
ax.set_xlabel('Daily Return')
ax.set_ylabel('Frequency')
ax.set_title('Distribution of Returns')
ax.legend()

# 3. Time series: Drawdown
ax = axes[1, 0]
drawdown = (cumulative_return - cumulative_return.expanding().max()) / (1 + cumulative_return.expanding().max())
ax.fill_between(drawdown.index, drawdown * 100, 0, alpha=0.5, color='red')
ax.set_ylabel('Drawdown (%)')
ax.set_title('Drawdown Over Time')
ax.grid(True, alpha=0.3)

# 4. Metrics table
ax = axes[1, 1]
ax.axis('off')
metrics_table = pd.DataFrame({
    'Metric': ['Annual Return', 'Volatility', 'Sharpe Ratio', 'Max Drawdown', 'Win Rate'],
    'Value': [f'{returns.mean()*252:.1%}', f'{returns.std()*np.sqrt(252):.1%}', 
              f'{sharpe:.2f}', f'{drawdown.min():.1%}', f'{(returns>0).mean():.1%}']
})
ax.table(cellText=metrics_table.values, colLabels=metrics_table.columns, 
         cellLoc='center', loc='center', bbox=[0, 0, 1, 1])
ax.set_title('Summary Metrics')

plt.tight_layout()
plt.savefig('backtest_report.png', dpi=150, bbox_inches='tight')
```

**When to Use:**
- ✅ Daily market reports
- ✅ Backtest visualization
- ✅ Stakeholder presentations

---

#### 4.4 Accessibility & Color

**What It Is:**  
Ensuring data is readable by everyone (color-blind, low vision, print, etc.).

**Guidelines:**

```python
import matplotlib.pyplot as plt

# BAD: Red-green (affects 8% of men, 0.5% of women)
colors_bad = ['red', 'green', 'yellow']

# GOOD: Color-blind friendly palette
from matplotlib.colors import ListedColormap
colors_good = ['#1b9e77', '#d95f02', '#7570b3']  # Tol palette

# Or use this palette
colors_accessible = {
    'blue': '#0173B2',
    'orange': '#DE8F05',
    'red': '#CC78BC',
    'teal': '#029E73',
    'cyan': '#56B4E9',
    'purple': '#F0E442',
}

# Example: Use distinct shades instead of red-green
fig, ax = plt.subplots()
ax.bar(['NSE', 'BSE'], [1.2, 0.8], color=['#0173B2', '#DE8F05'])
ax.set_ylabel('Daily Return (%)')
plt.show()

# Check accessibility
# Use: http://www.color-blindness.com/coblis-color-blindness-simulator/
# Simulate how your chart looks to color-blind people
```

**Applied to Your Reports:**

```python
# Bad: Red for down, green for up (confuses color-blind users)
def format_return(ret):
    color = 'red' if ret < 0 else 'green'
    return f"<span style='color:{color}'>{ret:.2%}</span>"

# Good: Use text + symbol + numeric
def format_return_accessible(ret):
    arrow = "↑" if ret > 0 else "↓"
    return f"{arrow} {ret:.2%}"

# Even better: Use table with text formatting
print(f"NSE: +1.2% (gainers outweigh losers)")
print(f"BSE: +0.8% (slight gain)")
```

**When to Use:**
- ✅ Every visualization
- ✅ Reports sent to stakeholders
- ✅ Dashboards

---

#### 4.5 Before/After Narratives

**What It Is:**  
Showing how a technique/strategy improved results.

**Structure:**

```
BEFORE (Old Approach):
├─ Darvas strategy only
├─ Result: +8.2% annual return
├─ Problem: Works in bull markets, loses in sideways markets

AFTER (New Approach):
├─ Regime-aware strategy (Darvas if trending, RSI if mean-reverting)
├─ Result: +12.4% annual return (+4.2% improvement)
├─ Benefit: Adapts to market character

EVIDENCE:
├─ 5-year backtest on NSE 500
├─ Out-of-sample Sharpe: 0.85 vs old 0.60
└─ 95% confidence this isn't luck (statistical significance test)
```

**Applied to Your Framework:**

```python
def compare_strategies(old_strategy, new_strategy, df):
    """Generate before/after narrative."""
    
    old_returns = backtest(old_strategy, df)
    new_returns = backtest(new_strategy, df)
    
    improvement = new_returns.mean() - old_returns.mean()
    
    print(f"""
BEFORE (Hardcoded Thresholds):
  Annual Return: {old_returns.mean()*252:.1%}
  Sharpe Ratio: {calculate_sharpe(old_returns):.2f}
  Max Drawdown: {calculate_max_dd(old_returns):.1%}

AFTER (Data-Driven Approach):
  Annual Return: {new_returns.mean()*252:.1%} (+{improvement*252:.1%})
  Sharpe Ratio: {calculate_sharpe(new_returns):.2f}
  Max Drawdown: {calculate_max_dd(new_returns):.1%}

KEY IMPROVEMENT:
  Strategy now adapts to market regime (trending vs mean-reverting)
  Avoids wrong trades in hostile markets
""")
```

**When to Use:**
- ✅ Validating new techniques
- ✅ Justifying changes to strategy
- ✅ Communicating value to stakeholders

---

### Key Takeaway from Knaflic

**"Without narrative, data is noise. Without data, narrative is fiction."**

Applied to Your System:
```python
# From Storytelling in framework
summary = Storytelling.summarize_backtest(returns, signals)
print(summary)
# Output: Narrative + metrics, not just numbers
```

---

## Integration Matrix

**How do the 4 books work together?**

```
                        Linoff           McKinney         Han/Kamber       Knaflic
                        (SQL/Excel)      (Python)         (Mining)         (Story)
┌──────────────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│ Data Ingestion       │ SQL queries  │ Pandas read  │ N/A          │ N/A          │
├──────────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Data Quality         │ Profiling ✓  │ isnull()     │ N/A          │ N/A          │
├──────────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Feature Engineering  │ Pivot tables │ Rolling ✓    │ Transforms   │ N/A          │
├──────────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Pattern Discovery    │ GROUP BY     │ Groupby ✓    │ Clustering ✓  │ N/A          │
├──────────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Modeling             │ SQL window fn│ sklearn prep │ Algorithms ✓  │ N/A          │
├──────────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Validation           │ Reconcile    │ Holdout      │ Cross-val ✓   │ N/A          │
├──────────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Reporting            │ N/A          │ N/A          │ N/A          │ Narrative ✓   │
└──────────────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

**Typical Workflow:**

```
1. Linoff (SQL):     Extract OHLCV from Cassandra, quality check
2. McKinney (Pandas): Feature engineer (lags, rolling, resampling)
3. Han/Kamber (Mine): Cluster stocks, find patterns, classify
4. Knaflic (Story):   Generate narrative backtest report
```

---

## Decision Trees: Which Tool When

### Decision Tree 1: Choosing Your Signal

```
What market character?
├─ TRENDING (Hurst > 0.55)
│  ├─ Use: Darvas Box (Linoff: thresholds, McKinney: MA200)
│  ├─ Avoid: RSI only (gives false signals in trends)
│  └─ Backtest: Walk-forward 252-day windows (Han/Kamber)
│
├─ MEAN-REVERTING (Hurst < 0.45)
│  ├─ Use: RSI, Bollinger Bands (McKinney: rolling)
│  ├─ Avoid: Darvas (chases up, catches down)
│  └─ Backtest: Walk-forward 252-day windows
│
└─ RANDOM (0.45 < Hurst < 0.55)
   ├─ Use: No strategy (or neutral)
   ├─ Why: No edge; expected return = 0
   └─ Action: Wait for regime change
```

### Decision Tree 2: Data Quality Issues

```
Missing data detected?
├─ How much?
│  ├─ <5%
│  │  └─ Action: Interpolate (McKinney: fillna)
│  ├─ 5-20%
│  │  └─ Action: Forward-fill then interpolate
│  └─ >20%
│     └─ Action: Drop column or rows
│
├─ Why missing?
│  ├─ Trading halt (known reason)
│  │  └─ Action: Forward-fill (assume price held)
│  ├─ Data error (unknown reason)
│  │  └─ Action: Flag for manual review (Linoff: quality report)
│  └─ Sparse data (young ticker)
│     └─ Action: Use group median (McKinney: groupby)
│
└─ Time series or cross-section?
   ├─ Time series
   │  └─ Action: ffill → interpolate (preserves trends)
   └─ Cross-section
      └─ Action: Mean/median fill (doesn't matter temporally)
```

### Decision Tree 3: Choosing Clustering Algorithm

```
How many samples?
├─ <1,000
│  └─ Algorithm: K-Means (fast)
├─ 1,000-100,000
│  ├─ If spherical clusters: K-Means
│  └─ If arbitrary shape: DBSCAN
└─ >100,000
   ├─ If must be fast: Mini-batch K-Means
   └─ If can wait: DBSCAN or Hierarchical

Do you know number of clusters K?
├─ Yes
│  └─ Use K-Means
├─ No
│  ├─ Use Elbow method to find K
│  └─ Or use DBSCAN (auto-finds clusters)

Outlier sensitivity?
├─ Important (want to find outliers)
│  └─ Use DBSCAN or Isolation Forest
├─ Not important (just grouping)
   └─ Use K-Means
```

---

## Advanced Techniques

### Technique 1: Ensemble Methods (Combining Multiple Signals)

**What It Is:**  
Instead of one signal, combine several predictions (Darvas + RSI + Volume).

**Methods:**

```python
# Voting: majority rule
def ensemble_vote(signals):
    """Combine signals via voting."""
    darvas_signal = TrendSignals.darvas_box(...)  # 0-10 score
    rsi_signal = MeanReversionSignals.rsi_signal(...)  # 0-10 score
    volume_signal = volume_breakout(...)  # 0-10 score
    
    # Simple average
    ensemble_score = (darvas_signal + rsi_signal + volume_signal) / 3
    
    # Weighted average (if you trust some signals more)
    ensemble_score = 0.5 * darvas_signal + 0.3 * rsi_signal + 0.2 * volume_signal
    
    return ensemble_score

# Stacking: Use meta-model
def ensemble_stacking(features):
    """Train model to learn signal weights."""
    X = np.column_stack([darvas_scores, rsi_scores, volume_scores])
    y = historical_actual_results
    
    # Train meta-model (e.g., logistic regression)
    meta_model = LogisticRegression()
    meta_model.fit(X, y)
    
    # Optimal weights = learned coefficients
    weights = meta_model.coef_[0]  # [0.5, 0.3, 0.2]
    
    # Apply
    final_signal = X @ weights
    return final_signal
```

**When to Use:**
- ✅ Reducing false signals (require multiple confirmations)
- ✅ Learning optimal signal weights from data

---

### Technique 2: Cross-Validation (Prevent Overfitting)

**What It Is:**  
Testing model on data it never saw during training.

**Methods:**

```python
from sklearn.model_selection import KFold, TimeSeriesSplit

# 1. K-Fold (NOT for time series; mixes past & future)
# BAD for trading
kfold = KFold(n_splits=5)
for train_idx, test_idx in kfold.split(df):
    X_train, X_test = X[train_idx], X[test_idx]
    # Problem: test set contains future data mixed with past

# 2. Time Series Split (GOOD for trading)
tscv = TimeSeriesSplit(n_splits=5)
for train_idx, test_idx in tscv.split(df):
    X_train, X_test = X[train_idx], X[test_idx]
    # Correct: train on [0:800], test on [800:900], repeat...
    model = train(X_train)
    score = evaluate(model, X_test)
    scores.append(score)

# 3. Walk-Forward (production-like)
train_window = 252
test_window = 63
for i in range(0, len(df) - train_window - test_window, 21):
    train_data = df[i:i+train_window]
    test_data = df[i+train_window:i+train_window+test_window]
    
    model = train(train_data)
    pred = model.predict(test_data)
    # Evaluate
```

**When to Use:**
- ✅ Every backtest (use Walk-Forward or TimeSeriesSplit)
- ✅ Never use K-Fold for time series

---

### Technique 3: Feature Importance Analysis

**What It Is:**  
Identifying which features actually matter for predictions.

**Methods:**

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance

# Method 1: Tree feature importance (built-in)
clf = RandomForestClassifier()
clf.fit(X_train, y_train)
importance = clf.feature_importances_

for feature, imp in zip(feature_names, importance):
    print(f"{feature}: {imp:.3f}")

# Method 2: Permutation importance (model-agnostic)
perm_importance = permutation_importance(clf, X_test, y_test)
for feature, imp in zip(feature_names, perm_importance.importances_mean):
    print(f"{feature}: {imp:.3f}")

# Method 3: SHAP values (explain individual predictions)
import shap
explainer = shap.TreeExplainer(clf)
shap_values = explainer.shap_values(X_test)
shap.summary_plot(shap_values, X_test)
```

**When to Use:**
- ✅ Understanding which signals matter
- ✅ Simplifying models (drop low-importance features)

---

### Technique 4: Hyperparameter Tuning

**What It Is:**  
Finding optimal parameters for your algorithm.

```python
from sklearn.model_selection import GridSearchCV

# Grid search: try all combinations
params = {
    'n_estimators': [50, 100, 200],
    'max_depth': [5, 10, 20],
    'min_samples_split': [2, 5, 10]
}

clf = GridSearchCV(RandomForestClassifier(), params, cv=5)
clf.fit(X_train, y_train)

print(f"Best params: {clf.best_params_}")
print(f"Best score: {clf.best_score_:.3f}")

# Random search: sample random combinations (faster for many params)
from sklearn.model_selection import RandomizedSearchCV
clf = RandomizedSearchCV(RandomForestClassifier(), params, n_iter=10, cv=5)
clf.fit(X_train, y_train)
```

**When to Use:**
- ✅ Optimizing algorithm parameters
- ✅ Improving backtest performance

---

## Anti-Patterns: What NOT to Do

### Anti-Pattern 1: In-Sample Optimization

**Problem:** Tuning parameters on the same data you test on.

```python
# WRONG: In-sample = overfitting
for threshold in [20, 25, 30, 35, 40]:
    returns = backtest(df, rsi_threshold=threshold)
    if returns > best_return:
        best_return = returns
        best_threshold = threshold  # ← Biased upward

# RIGHT: Out-of-sample = real
train_df = df[:2000]
test_df = df[2000:]

# Optimize on train
for threshold in [20, 25, 30, 35, 40]:
    returns = backtest(train_df, rsi_threshold=threshold)
    if returns > best_return:
        best_return = returns
        best_threshold = threshold

# Test on unseen data
final_return = backtest(test_df, rsi_threshold=best_threshold)
```

---

### Anti-Pattern 2: Look-Ahead Bias

**Problem:** Using future data to make past predictions.

```python
# WRONG: Future data leaks into past signals
prices['momentum'] = prices['close'].pct_change(5)  # 5-day forward return
prices['signal'] = np.where(prices['momentum'] > 0, 'BUY', 'SELL')

# Now: your signal knows the next 5 days (cheating!)

# RIGHT: Use lagged momentum
prices['momentum_past'] = prices['close'].shift(5).pct_change(5)  # Past 5-day return
prices['signal'] = np.where(prices['momentum_past'] > 0, 'BUY', 'SELL')

# Or: use forward-shifted signal
prices['return_forward_5d'] = prices['close'].pct_change(5).shift(-5)  # Actual future return
prices['signal'] = np.where(prices['close'].pct_change(5) > 0, 'BUY', 'SELL')
# Signal today, tested on tomorrow's data
```

---

### Anti-Pattern 3: Survivorship Bias

**Problem:** Only including stocks that survived to present day; ignoring bankrupt companies.

```python
# WRONG: Only include tickers still trading
tickers = ['RELIANCE', 'INFY', 'TCS', ...]  # All alive today
backtest_results = high  # ← Biased! Losers removed

# RIGHT: Include historical tickers (some may have delisted)
all_tickers = load_all_historical_tickers()  # 5000 tickers, 300 since delisted
backtest_results = more_realistic
```

**Impact:** Survivorship bias inflates historical returns by 1-2% annually.

---

### Anti-Pattern 4: Data Snooping

**Problem:** Testing too many strategies until one works by chance.

```python
# WRONG: Try 100 strategies on 1000 stocks
strategies = [rsi_threshold=20, 25, 30, ..., threshold=100]
for strat in strategies:
    result = backtest(strat)
    if result > benchmark:
        winner = strat  # ← Likely random chance

# Probability: 1 - (1 - 0.05)^100 = 99% that ≥1 strategy beats by luck!

# RIGHT: Limit tests or adjust significance threshold
# Bonferroni correction: p-value threshold = 0.05 / num_tests
if p_value < 0.05 / 100:  # 0.0005 instead of 0.05
    winner = strat  # Much harder to pass
```

---

### Anti-Pattern 5: Ignoring Regime Changes

**Problem:** Strategy works great in bull market, loses in bear market.

```python
# WRONG: Single strategy, all regimes
backtest_2020_2024(strategy='darvas')
# Returns +18% (but market was bullish)

# RIGHT: Regime-aware strategy
for year in range(2020, 2025):
    regime = detect_regime(df_year)
    if regime == 'BULL':
        return_year = backtest(strategy='darvas')
    elif regime == 'BEAR':
        return_year = backtest(strategy='defensive')
    else:
        return_year = backtest(strategy='neutral')
    
    total_return *= (1 + return_year)
# More realistic; accounts for regime shifts
```

---

## Summary Table: All Tools at a Glance

| Challenge | Linoff (SQL) | McKinney (Pandas) | Han/Kamber (Mining) | Knaflic (Story) |
|-----------|--------------|-------------------|---------------------|-----------------|
| **Data Quality** | Profiling ✓ | isnull() ✓ | N/A | N/A |
| **Feature Engineering** | Aggregation | Rolling ✓ | Transforms | N/A |
| **Pattern Discovery** | GROUP BY | Groupby ✓ | Clustering ✓ | N/A |
| **Classification** | Case statements | N/A | Tree, SVM ✓ | N/A |
| **Anomaly Detection** | Thresholds | Describe | Outlier alg ✓ | N/A |
| **Backtesting** | Reconcile | Holdout | Cross-val ✓ | N/A |
| **Reporting** | N/A | N/A | N/A | Narrative ✓ |

---

## Your Next Steps

1. **Linoff**: Set up daily data quality checks (SQL profiling)
2. **McKinney**: Master 3 rolling feature types (SMA, volatility, correlation)
3. **Han/Kamber**: Choose 1 clustering algorithm; test on your universe
4. **Knaflic**: Write 1 narrative backtest report
5. **Repeat quarterly** to stay sharp

---

**Status:** ✅ Comprehensive reference guide complete  
**Last Updated:** 2026-08-01  
**Your Action:** Pick ONE technique per week; master it before moving on
