#!/usr/bin/env python3
"""
edinet_individual_downloader.py — Download individual XBRL files from EDINET.

EDINET API provides access to individual filings. This script:
1. Lists filings for a date range using EDINET API
2. Filters for XBRL documents
3. Downloads each XBRL file individually
4. Packs into a ZIP for processing

Usage:
  python3 edinet_individual_downloader.py --period fy2024q3 --dest /tmp
  python3 edinet_individual_downloader.py --all-recent --dest /tmp
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import requests

sys.path.insert(0, '/Users/umashankar/market-pipeline/code/python_files')
import env_loader


def get_api_key() -> Optional[str]:
    """Load EDINET API key."""
    try:
        return env_loader.get('EDINET_API_KEY')
    except Exception as e:
        print(f"✗ Error loading credentials: {e}")
        return None


def list_filings(api_key: str, start_date: str, end_date: str, limit: int = 500) -> List[Dict]:
    """
    List all filings for a date range.

    Args:
      api_key: EDINET API key
      start_date: YYYY-MM-DD
      end_date: YYYY-MM-DD
      limit: Max results per page

    Returns: List of filing dictionaries
    """
    print(f"[INFO] Listing filings from {start_date} to {end_date}...")

    url = "https://disclosure2.edinet-fsa.go.jp/api/v2/filings"
    headers = {"X-API-KEY": api_key}
    params = {"date": start_date, "to_date": end_date}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            filings = data.get('filings', [])
            print(f"✓ Found {len(filings)} filings")
            return filings
        else:
            print(f"✗ API error: {resp.status_code}")
            if resp.status_code == 429:
                print("  Rate limited. Try again later.")
            return []
    except Exception as e:
        print(f"✗ Error: {e}")
        return []


def filter_xbrl_filings(filings: List[Dict]) -> List[Dict]:
    """Filter filings that have XBRL documents."""
    xbrl_filings = []

    for filing in filings:
        doc_id = filing.get('docID')
        company = filing.get('companyName')

        # Check if filing has XBRL
        if filing.get('hasXBRL'):
            xbrl_filings.append({
                'docID': doc_id,
                'company': company,
                'filing_date': filing.get('submitDateTime'),
                'period': filing.get('periodEnd'),
            })

    print(f"✓ Filtered to {len(xbrl_filings)} filings with XBRL")
    return xbrl_filings


def download_xbrl_file(api_key: str, doc_id: str, dest_dir: Path) -> Optional[str]:
    """
    Download XBRL file for a single filing.

    Returns: Path to downloaded file, or None if failed
    """
    url = f"https://disclosure2.edinet-fsa.go.jp/api/v2/documents/{doc_id}/xbrl"
    headers = {"X-API-KEY": api_key}

    try:
        resp = requests.get(url, headers=headers, timeout=30, stream=True)

        if resp.status_code == 200:
            # Filename from header or docID
            filename = f"{doc_id}.zip"
            filepath = dest_dir / filename

            # Download
            total_size = int(resp.headers.get('content-length', 0))
            downloaded = 0

            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            pct = (downloaded / total_size * 100)
                            print(f"    {pct:.1f}%", end="\r", flush=True)

            print(f"\n  ✓ {filename} ({filepath.stat().st_size / 1024:.1f} KB)")
            return str(filepath)

        elif resp.status_code == 404:
            print(f"  ✗ Not found (404)")
            return None
        else:
            print(f"  ✗ Error {resp.status_code}")
            return None

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None


def download_period(api_key: str, period: str, dest: Path) -> int:
    """
    Download all XBRL files for a specific period.

    Returns: Number of files downloaded
    """
    period_map = {
        'fy2023annual': ('2023-04-01', '2024-03-31', 'FY2023 Annual'),
        'fy2024q1': ('2024-04-01', '2024-06-30', 'FY2024 Q1'),
        'fy2024q2': ('2024-07-01', '2024-09-30', 'FY2024 Q2'),
        'fy2024q3': ('2024-10-01', '2024-12-31', 'FY2024 Q3'),
    }

    if period not in period_map:
        print(f"✗ Unknown period: {period}")
        return 0

    start_date, end_date, label = period_map[period]

    print(f"\n{'='*70}")
    print(f"Downloading {label} ({start_date} to {end_date})")
    print(f"{'='*70}")

    # List filings
    filings = list_filings(api_key, start_date, end_date)
    if not filings:
        return 0

    # Filter for XBRL
    xbrl_filings = filter_xbrl_filings(filings)
    if not xbrl_filings:
        print("✗ No XBRL filings found")
        return 0

    # Download each
    print(f"\n[INFO] Downloading {len(xbrl_filings)} individual XBRL files...")

    success_count = 0
    for idx, filing in enumerate(xbrl_filings, 1):
        doc_id = filing['docID']
        company = filing['company']
        print(f"  [{idx}/{len(xbrl_filings)}] {company}")

        if download_xbrl_file(api_key, doc_id, dest):
            success_count += 1

    print(f"\n✓ Downloaded {success_count}/{len(xbrl_filings)} files")
    return success_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", type=str,
                        choices=['fy2023annual', 'fy2024q1', 'fy2024q2', 'fy2024q3'],
                        help="Download specific period")
    parser.add_argument("--all-recent", action="store_true",
                        help="Download all recent periods (FY2023-2024)")
    parser.add_argument("--dest", type=str, default="/tmp",
                        help="Destination directory")

    args = parser.parse_args()

    print("=" * 70)
    print("EDINET Individual XBRL Downloader")
    print("=" * 70)
    print()

    # Load API key
    api_key = get_api_key()
    if not api_key:
        print("✗ EDINET_API_KEY not found")
        sys.exit(1)

    # Create dest dir
    dest = Path(args.dest)
    if not dest.exists():
        print(f"✗ Directory not found: {dest}")
        sys.exit(1)

    total_downloaded = 0

    # Download by period
    if args.period:
        total_downloaded = download_period(api_key, args.period, dest)

    elif args.all_recent:
        periods = ['fy2023annual', 'fy2024q1', 'fy2024q2', 'fy2024q3']
        for period in periods:
            total_downloaded += download_period(api_key, period, dest)

    else:
        parser.print_help()
        return

    print()
    print("=" * 70)
    print(f"Total downloaded: {total_downloaded} files")
    print("=" * 70)

    if total_downloaded > 0:
        print(f"\nNext: Process individual files or consolidate with:")
        print(f"  python3 scripts/consolidate_individual_xbrl.py --src {dest}")


if __name__ == "__main__":
    main()
