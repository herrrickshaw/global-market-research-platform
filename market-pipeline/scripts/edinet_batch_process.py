#!/usr/bin/env python3
"""
edinet_batch_process.py — Process individual EDINET XBRL downloads into Postgres.

Takes individual XBRL files (as downloaded by edinet_individual_downloader.py)
and processes them into the database.

Usage:
  python3 edinet_batch_process.py --src /tmp --pattern "*.zip"
  python3 edinet_batch_process.py --src /tmp --archive dropbox:/path/
"""

import argparse
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, '/Users/umashankar/market-pipeline/code/python_files')
from edinet_xbrl_historical_fetcher import process_xbrl_zip, store_postgres


def find_xbrl_files(src_dir: Path, pattern: str = "*.zip") -> List[Path]:
    """Find all XBRL ZIP files matching pattern."""
    print(f"[INFO] Scanning {src_dir} for {pattern}...")

    files = sorted(src_dir.glob(pattern))
    files = [f for f in files if f.is_file()]

    print(f"✓ Found {len(files)} files")
    return files


def process_batch(files: List[Path]) -> int:
    """
    Process all files, consolidate results into Postgres.

    Returns: Total rows inserted
    """
    print(f"\n[INFO] Processing {len(files)} XBRL files...")

    total_rows = 0

    for idx, filepath in enumerate(files, 1):
        filename = filepath.name
        print(f"\n  [{idx}/{len(files)}] {filename}")

        try:
            # Parse XBRL
            df = process_xbrl_zip(str(filepath))

            if df.empty:
                print(f"    ✗ No data extracted")
                continue

            rows = len(df)
            print(f"    ✓ Extracted {rows} company-quarters")

            # Load to Postgres
            store_postgres(df)
            total_rows += rows

        except Exception as e:
            print(f"    ✗ Error: {e}")
            continue

    return total_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=str, required=True,
                        help="Source directory with XBRL ZIPs")
    parser.add_argument("--pattern", type=str, default="*.zip",
                        help="File pattern to match (default: *.zip)")
    parser.add_argument("--archive", type=str,
                        help="Archive to cloud after processing (dropbox:/path/ or gdrive:/path/)")

    args = parser.parse_args()

    print("=" * 70)
    print("EDINET Batch XBRL Processor")
    print("=" * 70)
    print()

    # Find files
    src = Path(args.src)
    if not src.exists():
        print(f"✗ Directory not found: {src}")
        sys.exit(1)

    files = find_xbrl_files(src, args.pattern)
    if not files:
        print("✗ No files found")
        sys.exit(1)

    # Process
    total = process_batch(files)

    print()
    print("=" * 70)
    print(f"Processing complete: {total} rows loaded to Postgres")
    print("=" * 70)

    # Archive if requested
    if args.archive:
        print(f"\n[INFO] Archiving to {args.archive}...")
        print("  TODO: Implement cloud archival via rclone")
        for filepath in files:
            print(f"    rclone move {filepath} {args.archive}")


if __name__ == "__main__":
    main()
