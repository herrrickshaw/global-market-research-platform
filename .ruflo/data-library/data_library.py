#!/usr/bin/env python3
"""
Data Library: Unified access to all datasets across 40+ repositories.

Manages inventory of:
- Local machine storage (market-pipeline, global-market-data, etc.)
- Dropbox archives (market-data-archive, market-data-backup)
- DuckDB tables (market_data.duckdb with 966 European stocks, NSE/BSE, etc.)
- Cassandra keyspaces (herrrickshaw with 5-market OHLCV+RSI)
- Online sources (NSE, SEC, SEBI, MOSPI, etc.)

Provides:
- Unified query interface: lib.search("india ohlcv", market="india")
- Gap identification: lib.gaps("india", date_from="2026-01-01")
- Cost-optimal paths: lib.get_optimal("data_name", latency="<100ms")
- Freshness tracking: lib.freshness_report()
- Collector status: lib.collectors_status()
"""

import os
import json
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import subprocess

class DataLibrary:
    def __init__(self, registry_path="/Users/umashankar/.ruflo/data-library"):
        self.registry_path = Path(registry_path)
        self.db_path = self.registry_path / "data_catalog.db"
        self.manifest_path = self.registry_path / "storage_manifest.json"
        self.gaps_report_path = self.registry_path / "data_quality_report.md"
        self.collectors_path = self.registry_path / "collectors_status.parquet"

        self._init_db()
        self._load_manifest()

    def _init_db(self):
        """Initialize SQLite database with schema."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")

        # Datasets table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                source TEXT,
                market TEXT,
                asset_class TEXT,

                -- Storage locations
                local_path TEXT,
                dropbox_path TEXT,
                online_url TEXT,
                cassandra_table TEXT,
                duckdb_table TEXT,

                -- Storage tier (priority: local → dropbox → cassandra → duckdb → online)
                storage_tier TEXT,

                -- Data freshness & quality
                last_updated DATETIME,
                freshness_hours INTEGER,
                row_count INTEGER,
                size_mb REAL,
                completeness_pct REAL,
                quality_score INTEGER,

                -- Coverage
                date_from DATE,
                date_to DATE,
                symbols_covered TEXT,
                missing_symbols TEXT,

                -- Metadata
                collector_name TEXT,
                collector_status TEXT,
                update_frequency TEXT,
                cost_to_fetch TEXT,
                latency_ms INTEGER,

                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Data gaps table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS data_gaps (
                gap_id TEXT PRIMARY KEY,
                dataset_id TEXT NOT NULL,
                gap_type TEXT,
                description TEXT,
                missing_date_ranges TEXT,
                missing_symbols TEXT,
                impact_score INTEGER,
                recommended_action TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id)
            )
        """)

        # Collector pipeline status
        conn.execute("""
            CREATE TABLE IF NOT EXISTS collectors (
                collector_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                repo TEXT,
                last_run DATETIME,
                next_scheduled_run DATETIME,
                status TEXT,
                records_ingested INTEGER,
                errors INTEGER,
                datasets_produced TEXT,
                frequency TEXT,
                timeout_seconds INTEGER,
                cost_per_run TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Storage manifest table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS storage_backends (
                backend_id TEXT PRIMARY KEY,
                name TEXT,
                location TEXT,
                type TEXT,
                size_mb REAL,
                latency_ms INTEGER,
                cost TEXT,
                availability TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def _load_manifest(self):
        """Load storage manifest."""
        if self.manifest_path.exists():
            with open(self.manifest_path) as f:
                self.manifest = json.load(f)
        else:
            self.manifest = self._default_manifest()
            self._save_manifest()

    def _default_manifest(self) -> Dict:
        """Default storage locations across the platform."""
        return {
            "local": {
                "market-pipeline": "/Users/umashankar/market-pipeline",
                "global-market-data": "/Users/umashankar/global-market-data",
                "global-stock-screener": "/Users/umashankar/global-stock-screener",
                "put-call-parity": "/Users/umashankar/put-call-parity",
            },
            "dropbox": {
                "market-data-archive": "Dropbox/market-data-archive",
                "market-data-backup": "Dropbox/market-data-backup",
            },
            "databases": {
                "cassandra": {
                    "host": "localhost",
                    "port": 9042,
                    "keyspace": "herrrickshaw",
                    "tables": [
                        "instruments", "instruments_by_symbol", "instruments_by_name",
                        "stock_quotes", "price_history", "seed_status"
                    ]
                },
                "duckdb": {
                    "path": "/Users/umashankar/market-pipeline/code/python_files/data/market_data.duckdb",
                    "tables": [
                        "europe_all_list", "frankfurt_list", "london_list",
                        "nse_stocks_fundamental", "bse_stocks_fundamental",
                        "all_stocks_combined"
                    ]
                },
                "sqlite": {
                    "path": "/Users/umashankar/.ruflo/data/token_usage.db",
                    "tables": ["token_usage"]
                }
            },
            "online": {
                "nse": "https://www.nseindia.com",
                "sec_edgar": "https://www.sec.gov/cgi-bin/browse-edgar",
                "sebi": "https://www.sebi.gov.in",
                "mospi_ndap": "https://data.gov.in/resource",
                "yfinance": "https://finance.yahoo.com",
            }
        }

    def _save_manifest(self):
        """Save manifest to disk."""
        with open(self.manifest_path, 'w') as f:
            json.dump(self.manifest, f, indent=2)

    def add_dataset(self, dataset_id: str, name: str, **kwargs) -> bool:
        """Add a dataset to the catalog."""
        try:
            conn = sqlite3.connect(self.db_path)

            # Set defaults
            kwargs['dataset_id'] = dataset_id
            kwargs['name'] = name
            kwargs['updated_at'] = datetime.now().isoformat()

            # Insert or replace
            cols = ', '.join(kwargs.keys())
            placeholders = ', '.join(['?' for _ in kwargs])
            conn.execute(
                f"INSERT OR REPLACE INTO datasets ({cols}) VALUES ({placeholders})",
                tuple(kwargs.values())
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error adding dataset {dataset_id}: {e}")
            return False

    def search(self, query: str, market: Optional[str] = None, asset_class: Optional[str] = None) -> List[Dict]:
        """Search datasets by name or description."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        sql = "SELECT * FROM datasets WHERE (name LIKE ? OR description LIKE ?)"
        params = [f"%{query}%", f"%{query}%"]

        if market:
            sql += " AND market = ?"
            params.append(market)
        if asset_class:
            sql += " AND asset_class = ?"
            params.append(asset_class)

        results = conn.execute(sql, params).fetchall()
        conn.close()

        return [dict(row) for row in results]

    def gaps(self, market: str, date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict:
        """Identify data gaps for a market."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        gaps = conn.execute(
            "SELECT * FROM data_gaps WHERE dataset_id IN (SELECT dataset_id FROM datasets WHERE market = ?)",
            (market,)
        ).fetchall()
        conn.close()

        return {
            "market": market,
            "total_gaps": len(gaps),
            "gaps": [dict(g) for g in gaps],
            "completeness_pct": self._estimate_completeness(market)
        }

    def _estimate_completeness(self, market: str) -> float:
        """Estimate data completeness for a market."""
        conn = sqlite3.connect(self.db_path)

        result = conn.execute(
            "SELECT AVG(completeness_pct) as avg_completeness FROM datasets WHERE market = ?",
            (market,)
        ).fetchone()
        conn.close()

        return result[0] if result[0] else 0.0

    def get_optimal(self, dataset_name: str, latency: str = "<1000ms", freshness: str = "<7days") -> Optional[Dict]:
        """Get optimal storage path based on latency and freshness requirements."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # Parse requirements
        latency_ms = int(latency.replace("<", "").replace("ms", "")) if "<" in latency else 1000
        freshness_hours = int(freshness.replace("<", "").replace("days", "")) * 24 if "days" in freshness else 168

        # Find datasets matching query
        results = conn.execute(
            "SELECT * FROM datasets WHERE name LIKE ? ORDER BY storage_tier ASC, latency_ms ASC",
            (f"%{dataset_name}%",)
        ).fetchall()
        conn.close()

        # Return first match that meets latency requirement
        for row in results:
            if row['latency_ms'] and row['latency_ms'] <= latency_ms:
                if row['freshness_hours'] and row['freshness_hours'] <= freshness_hours:
                    return dict(row)

        # Fallback: return first available
        return dict(results[0]) if results else None

    def get(self, dataset_id: str) -> Optional[Dict]:
        """Get a specific dataset by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        result = conn.execute(
            "SELECT * FROM datasets WHERE dataset_id = ?",
            (dataset_id,)
        ).fetchone()
        conn.close()

        return dict(result) if result else None

    def lineage(self, symbol: str) -> List[Dict]:
        """Trace data lineage for a symbol (source → storage → analysis → output)."""
        # This would trace through NSE → bhavcopy_history → Cassandra → daily_scan → watchlist_mailer
        # Simplified version for now
        lineage = []
        conn = sqlite3.connect(self.db_path)

        # Find all datasets containing this symbol
        results = conn.execute(
            "SELECT * FROM datasets WHERE symbols_covered LIKE ? OR (symbols_covered IS NULL)",
            (f"%{symbol}%",)
        ).fetchall()
        conn.close()

        for row in results:
            lineage.append({
                "stage": "dataset",
                "name": row[1],
                "source": row[3],
                "collector": row[16]
            })

        return lineage

    def collectors_status(self) -> List[Dict]:
        """Get status of all data collectors."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        collectors = conn.execute("SELECT * FROM collectors ORDER BY last_run DESC").fetchall()
        conn.close()

        return [dict(c) for c in collectors]

    def freshness_report(self) -> pd.DataFrame:
        """Generate freshness report for all datasets."""
        conn = sqlite3.connect(self.db_path)

        df = pd.read_sql_query(
            "SELECT name, market, last_updated, freshness_hours, completeness_pct, quality_score FROM datasets ORDER BY freshness_hours ASC",
            conn
        )
        conn.close()

        return df

    def gaps_by_action(self) -> List[Dict]:
        """List gaps prioritized by impact and recommended action."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        gaps = conn.execute(
            "SELECT * FROM data_gaps ORDER BY impact_score DESC"
        ).fetchall()
        conn.close()

        return [dict(g) for g in gaps]

    def add_collector(self, collector_id: str, name: str, **kwargs) -> bool:
        """Register a data collector pipeline."""
        try:
            conn = sqlite3.connect(self.db_path)

            kwargs['collector_id'] = collector_id
            kwargs['name'] = name
            kwargs['updated_at'] = datetime.now().isoformat()

            cols = ', '.join(kwargs.keys())
            placeholders = ', '.join(['?' for _ in kwargs])
            conn.execute(
                f"INSERT OR REPLACE INTO collectors ({cols}) VALUES ({placeholders})",
                tuple(kwargs.values())
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error adding collector {collector_id}: {e}")
            return False

    def export_catalog(self, format: str = "parquet") -> str:
        """Export catalog to Parquet for external analysis."""
        df = pd.read_sql_query("SELECT * FROM datasets", sqlite3.connect(self.db_path))

        output_path = self.registry_path / f"data_catalog.{format}"
        df.to_parquet(str(output_path), index=False)

        return str(output_path)


if __name__ == "__main__":
    lib = DataLibrary()

    # Example usage
    print("Data Library initialized")
    print(f"Registry path: {lib.registry_path}")
    print(f"Database: {lib.db_path}")
