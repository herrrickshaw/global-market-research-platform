<!-- 
DATA LIBRARY LINK - Add this section to every repo README.md
This snippet provides discovery and documentation links.
-->

## 📊 Data Discovery

This repository is part of the **Global Data Library** — a unified catalog of 10,528 datasets across 40+ repositories.

### Quick Links

- **[Global Data Library README](.ruflo/DATA_LIBRARY_README.md)** — Full catalog, search API, and usage examples
- **[Data Library Python Interface](.ruflo/data-library/data_library.py)** — Query datasets programmatically
- **[Repository Scanner](.ruflo/data-library/repo_scanner.py)** — Reindex all repos to update the catalog

### Datasets in This Repository

The data catalog automatically inventories all datasets in this repo. To find your data:

```python
from data_library import DataLibrary

lib = DataLibrary()

# Search this repo's datasets
results = lib.search("", source="<repo-name>")

# Get dataset details
dataset = lib.get("<dataset_id>")
print(f"Rows: {dataset['row_count']}")
print(f"Freshness: {dataset['freshness_hours']} hours old")
print(f"Storage: {dataset['storage_tier']}")
```

### Browse the Full Catalog

**Market Coverage** (5 markets, 21,279 symbols):
- India (NSE/BSE): 2,364 instruments
- US (NASDAQ/NYSE): 7,442 instruments
- Europe (17 exchanges): 1,214 instruments
- Japan (TSE): 3,709 instruments
- Korea (KRX): 2,768 instruments

**Government Sources** (30+ ministries):
- MOSPI: 25 datasets (GDP, CPI, trade, agri, power)
- SEBI: 151,928 XBRL results + IPO pipeline
- PIB: 25+ ministry announcements
- DGFT: India trade data (monthly)
- Agmarknet: 300+ mandi prices (daily)
- NSE/MCX: Real-time derivatives chains

See [Global Data Library README](.ruflo/DATA_LIBRARY_README.md) for complete documentation.

### Finding Data Across All Repos

```python
# Find India OHLCV data (might be in multiple repos)
lib.search("india ohlcv", market="india")

# Get the fastest/freshest version
optimal = lib.get_optimal("india ohlcv", latency="<100ms", freshness="<1day")
# Returns: {"storage_tier": "cassandra", "path": "..."}

# Check data gaps
gaps = lib.gaps("india", date_from="2026-01-01")

# See which collectors are stale
status = lib.collectors_status()
```

---
