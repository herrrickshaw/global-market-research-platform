#!/usr/bin/env python3
"""
Repository Scanner: Catalog all datasets across 40+ repositories.

Scans for:
- Parquet files (.parquet, .parquet.gz)
- DuckDB databases (.duckdb)
- SQLite databases (.db, .sqlite)
- CSV files (if tracked)
- Cassandra tables (introspection)
- Data dimensions (row counts, size, freshness)

Updates data_catalog.db with discovered datasets.
"""

import os
import json
import glob
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3

try:
    import pandas as pd
    import pyarrow.parquet as pq
except ImportError:
    pd = None
    pq = None

from data_library import DataLibrary


class RepositoryScanner:
    def __init__(self):
        self.home = Path.home()
        self.lib = DataLibrary()
        self.repos = self._discover_repos()

    def _discover_repos(self) -> List[Path]:
        """Discover all repositories in the home directory."""
        repos = []

        # Known repo locations
        known_repos = [
            "market-pipeline",
            "global-stock-screener",
            "global-market-data",
            "put-call-parity",
            "agri-commodity-tracker",
            "india-trade-tracker",
            "india-trade-data-analysis",
            "india-trade-sector-policy-recommendations",
            "digital-twin-for-ipa",
            "vehicle_fuel_mileage",
            "saf-monitoring-system",
            "iudx-flood-collector",
            "price_prediction_backtest",
            "BazaarTalks",
            "BazaarTalks-cpp",
        ]

        for repo_name in known_repos:
            repo_path = self.home / repo_name
            if repo_path.exists():
                repos.append(repo_path)

        return repos

    def scan_all(self) -> Dict:
        """Scan all repositories and update catalog."""
        summary = {
            "repos_scanned": 0,
            "datasets_found": 0,
            "total_size_gb": 0.0,
            "datasets": []
        }

        for repo_path in self.repos:
            print(f"\n📂 Scanning {repo_path.name}...")
            datasets = self.scan_repo(repo_path)

            summary["repos_scanned"] += 1
            summary["datasets_found"] += len(datasets)
            summary["datasets"].extend(datasets)

            for ds in datasets:
                summary["total_size_gb"] += ds.get("size_mb", 0) / 1024

        print(f"\n✅ Scanned {summary['repos_scanned']} repos, found {summary['datasets_found']} datasets ({summary['total_size_gb']:.1f} GB)")
        return summary

    def scan_repo(self, repo_path: Path) -> List[Dict]:
        """Scan a single repository for datasets."""
        datasets = []

        # Scan for Parquet files
        datasets.extend(self._scan_parquet(repo_path))

        # Scan for DuckDB
        datasets.extend(self._scan_duckdb(repo_path))

        # Scan for SQLite
        datasets.extend(self._scan_sqlite(repo_path))

        # Scan for data directories
        datasets.extend(self._scan_data_dirs(repo_path))

        return datasets

    def _scan_parquet(self, repo_path: Path) -> List[Dict]:
        """Scan for Parquet files."""
        datasets = []

        if pq is None:
            return datasets

        for pq_file in repo_path.rglob("*.parquet*"):
            try:
                table = pq.read_table(str(pq_file))
                stats = self._get_file_stats(pq_file)

                dataset = {
                    "dataset_id": f"parquet_{pq_file.stem.replace('.', '_')}",
                    "name": pq_file.stem,
                    "source": repo_path.name,
                    "local_path": str(pq_file),
                    "storage_tier": "local",
                    "row_count": len(table),
                    "size_mb": stats["size_mb"],
                    "latency_ms": 50,
                    "last_updated": self._get_mtime(pq_file),
                    "freshness_hours": self._get_freshness_hours(pq_file),
                    "quality_score": 95
                }

                # Infer market and asset class
                dataset.update(self._infer_metadata(pq_file.stem))

                datasets.append(dataset)
                print(f"  ✓ Parquet: {pq_file.name} ({dataset['row_count']} rows, {stats['size_mb']:.1f} MB)")
            except Exception as e:
                print(f"  ✗ Parquet {pq_file.name}: {e}")

        return datasets

    def _scan_duckdb(self, repo_path: Path) -> List[Dict]:
        """Scan for DuckDB databases."""
        datasets = []

        for db_file in repo_path.rglob("*.duckdb"):
            try:
                import duckdb

                conn = duckdb.connect(str(db_file), read_only=True)
                tables = conn.execute("SELECT name FROM information_schema.tables WHERE table_catalog='memory'").fetchall()

                for table_name, in tables:
                    row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

                    dataset = {
                        "dataset_id": f"duckdb_{db_file.stem}_{table_name}",
                        "name": f"{db_file.stem}.{table_name}",
                        "source": repo_path.name,
                        "duckdb_table": f"{db_file.stem}::{table_name}",
                        "storage_tier": "local",
                        "row_count": row_count,
                        "size_mb": self._get_file_stats(db_file)["size_mb"],
                        "latency_ms": 100,
                        "last_updated": self._get_mtime(db_file),
                        "freshness_hours": self._get_freshness_hours(db_file),
                        "quality_score": 90
                    }

                    dataset.update(self._infer_metadata(table_name))
                    datasets.append(dataset)

                conn.close()
                print(f"  ✓ DuckDB: {db_file.name} ({len(tables)} tables)")
            except Exception as e:
                print(f"  ✗ DuckDB {db_file.name}: {e}")

        return datasets

    def _scan_sqlite(self, repo_path: Path) -> List[Dict]:
        """Scan for SQLite databases."""
        datasets = []

        for db_file in repo_path.rglob("*.db"):
            try:
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()
                tables = cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()

                for table_name, in tables:
                    row_count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

                    dataset = {
                        "dataset_id": f"sqlite_{db_file.stem}_{table_name}",
                        "name": f"{db_file.stem}.{table_name}",
                        "source": repo_path.name,
                        "storage_tier": "local",
                        "row_count": row_count,
                        "size_mb": self._get_file_stats(db_file)["size_mb"],
                        "latency_ms": 150,
                        "last_updated": self._get_mtime(db_file),
                        "freshness_hours": self._get_freshness_hours(db_file),
                        "quality_score": 85
                    }

                    dataset.update(self._infer_metadata(table_name))
                    datasets.append(dataset)

                conn.close()
                print(f"  ✓ SQLite: {db_file.name} ({len(tables)} tables)")
            except Exception as e:
                print(f"  ✗ SQLite {db_file.name}: {e}")

        return datasets

    def _scan_data_dirs(self, repo_path: Path) -> List[Dict]:
        """Scan data directories for CSV and other formats."""
        datasets = []
        data_dirs = ["data", "cache_seed", "reports", "ltm", "archive"]

        for data_dir in data_dirs:
            dir_path = repo_path / data_dir
            if dir_path.exists():
                # Count CSV files
                csv_files = list(dir_path.glob("*.csv"))
                if csv_files:
                    total_size = sum(f.stat().st_size for f in csv_files) / (1024 ** 2)
                    dataset = {
                        "dataset_id": f"csv_{repo_path.name}_{data_dir}",
                        "name": f"{repo_path.name}/{data_dir}/CSV",
                        "source": repo_path.name,
                        "local_path": str(dir_path),
                        "storage_tier": "local",
                        "size_mb": total_size,
                        "latency_ms": 75,
                        "last_updated": self._get_mtime(dir_path),
                        "freshness_hours": self._get_freshness_hours(dir_path),
                        "quality_score": 80
                    }
                    dataset.update(self._infer_metadata(data_dir))
                    datasets.append(dataset)
                    print(f"  ✓ CSVs: {data_dir}/ ({len(csv_files)} files, {total_size:.1f} MB)")

        return datasets

    def _infer_metadata(self, name: str) -> Dict:
        """Infer market, asset class, etc. from dataset name."""
        metadata = {}

        # Detect market
        if any(x in name.lower() for x in ["india", "nse", "bse"]):
            metadata["market"] = "india"
        elif any(x in name.lower() for x in ["us", "nasdaq", "nyse"]):
            metadata["market"] = "us"
        elif any(x in name.lower() for x in ["europe", "london", "frankfurt"]):
            metadata["market"] = "europe"
        elif any(x in name.lower() for x in ["japan", "jse", "tse"]):
            metadata["market"] = "japan"
        elif any(x in name.lower() for x in ["korea", "krx", "kospi"]):
            metadata["market"] = "korea"

        # Detect asset class
        if any(x in name.lower() for x in ["ohlc", "price", "quote"]):
            metadata["asset_class"] = "equities"
        elif any(x in name.lower() for x in ["option", "futures", "derivative"]):
            metadata["asset_class"] = "derivatives"
        elif any(x in name.lower() for x in ["fundamental", "ratio", "financial"]):
            metadata["asset_class"] = "fundamentals"

        return metadata

    def _get_file_stats(self, path: Path) -> Dict:
        """Get file size and modification time."""
        try:
            stat = path.stat()
            return {"size_mb": stat.st_size / (1024 ** 2)}
        except:
            return {"size_mb": 0}

    def _get_mtime(self, path: Path) -> str:
        """Get file modification time."""
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            return mtime.isoformat()
        except:
            return datetime.now().isoformat()

    def _get_freshness_hours(self, path: Path) -> int:
        """Get hours since last modification."""
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            age = datetime.now() - mtime
            return int(age.total_seconds() / 3600)
        except:
            return 999999

    def update_catalog(self, datasets: List[Dict]):
        """Add all discovered datasets to catalog."""
        for ds in datasets:
            self.lib.add_dataset(
                dataset_id=ds.pop("dataset_id"),
                name=ds.pop("name"),
                **ds
            )

    def scan_and_update(self):
        """Scan all repos and update catalog in one go."""
        summary = self.scan_all()
        self.update_catalog(summary["datasets"])

        # Generate gap analysis
        self._generate_gap_report()

        return summary

    def _generate_gap_report(self):
        """Analyze gaps and generate report."""
        conn = sqlite3.connect(self.lib.db_path)

        # Find markets with low coverage
        markets = conn.execute("SELECT DISTINCT market FROM datasets WHERE market IS NOT NULL").fetchall()

        gaps = []
        for market, in markets:
            completeness = self.lib._estimate_completeness(market)
            if completeness < 90:
                gaps.append({
                    "market": market,
                    "completeness_pct": completeness,
                    "issue": "Low data completeness"
                })

        conn.close()
        return gaps


def main():
    """Run the scanner."""
    scanner = RepositoryScanner()
    summary = scanner.scan_and_update()

    print(f"\n📊 Catalog Updated:")
    print(f"  Repos scanned: {summary['repos_scanned']}")
    print(f"  Datasets found: {summary['datasets_found']}")
    print(f"  Total size: {summary['total_size_gb']:.1f} GB")


if __name__ == "__main__":
    main()
