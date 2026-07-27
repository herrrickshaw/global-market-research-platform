#!/usr/bin/env python3
"""
edinet_auto_download.py — Automated EDINET XBRL bulk file downloader.

Uses EDINET API to list and download quarterly XBRL bulk archives.

Usage:
  python3 edinet_auto_download.py --period fy2024q3           # Latest quarter
  python3 edinet_auto_download.py --all-recent                # FY2023 + 2024 Q1-Q3
  python3 edinet_auto_download.py --validate-api              # Test API connectivity
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

# Add code dir to path for env_loader
sys.path.insert(0, '/Users/umashankar/market-pipeline/code/python_files')
import env_loader


def get_api_key():
    """Load EDINET API key from credentials."""
    try:
        return env_loader.get('EDINET_API_KEY')
    except Exception as e:
        print(f"✗ Error loading credentials: {e}")
        return None


def validate_api(api_key: str) -> bool:
    """Test EDINET API connectivity."""
    print("[INFO] Testing EDINET API connectivity...")

    url = "https://disclosure2.edinet-fsa.go.jp/api/v2/filings"
    headers = {"X-API-KEY": api_key}
    params = {"limit": 1}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            print(f"✓ API connected successfully")
            return True
        elif resp.status_code == 403:
            print(f"✗ API key rejected (403 Forbidden)")
            return False
        else:
            print(f"✗ API error: {resp.status_code} {resp.reason}")
            return False
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False


def list_filings_by_period(api_key: str, period: str) -> dict:
    """
    Fetch filing list for a specific period.

    Period options:
      - fy2023annual: FY2023 Annual
      - fy2024q1: FY2024 Q1
      - fy2024q2: FY2024 Q2
      - fy2024q3: FY2024 Q3
    """

    period_map = {
        'fy2023annual': ('2023-04-01', '2024-03-31', 'FY2023'),
        'fy2024q1': ('2024-04-01', '2024-06-30', 'FY2024Q1'),
        'fy2024q2': ('2024-07-01', '2024-09-30', 'FY2024Q2'),
        'fy2024q3': ('2024-10-01', '2024-12-31', 'FY2024Q3'),
    }

    if period not in period_map:
        print(f"✗ Unknown period: {period}")
        print(f"  Options: {', '.join(period_map.keys())}")
        return {}

    from_date, to_date, label = period_map[period]

    print(f"[INFO] Fetching {label} filings ({from_date} to {to_date})...")

    url = "https://disclosure2.edinet-fsa.go.jp/api/v2/filings"
    headers = {"X-API-KEY": api_key}
    params = {
        "date": from_date,
        "to_date": to_date,
        "type": "4",  # Type 4 = Quarterly reports with XBRL
        "has_xbrl": "true",
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 200:
            filings = resp.json()
            print(f"✓ Found {len(filings.get('filings', []))} filings")
            return {"label": label, "filings": filings}
        else:
            print(f"✗ API error: {resp.status_code}")
            return {}
    except Exception as e:
        print(f"✗ Error fetching filings: {e}")
        return {}


def download_xbrl_bulk(api_key: str, period: str, dest: str = "/tmp") -> bool:
    """
    Download bulk XBRL ZIP for a period.

    EDINET may expose bulk downloads via a different endpoint.
    This function attempts to construct or find the bulk file URL.
    """

    period_map = {
        'fy2023annual': 'EDINET_XBRL_2023_all.zip',
        'fy2024q1': 'EDINET_XBRL_2024Q1_all.zip',
        'fy2024q2': 'EDINET_XBRL_2024Q2_all.zip',
        'fy2024q3': 'EDINET_XBRL_2024Q3_all.zip',
    }

    if period not in period_map:
        print(f"✗ Unknown period: {period}")
        return False

    filename = period_map[period]
    dest_path = Path(dest) / filename

    # EDINET bulk download URL structure (estimated)
    # This may need adjustment based on actual EDINET API documentation
    url = f"https://disclosure2.edinet-fsa.go.jp/XBRL/2024q3/{filename}"

    # Try alternative constructions
    urls_to_try = [
        url,
        f"https://disclosure.edinet-fsa.go.jp/api/v2/documents/bulk",
    ]

    headers = {"X-API-KEY": api_key, "User-Agent": "Mozilla/5.0"}

    for attempt_url in urls_to_try:
        print(f"[INFO] Attempting download from: {attempt_url}")

        try:
            resp = requests.get(attempt_url, headers=headers, timeout=60, stream=True)

            if resp.status_code == 200:
                total_size = int(resp.headers.get('content-length', 0))
                downloaded = 0

                print(f"[INFO] Downloading {filename} ({total_size / 1024 / 1024:.0f} MB)...")

                with open(dest_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            pct = (downloaded / total_size * 100) if total_size else 0
                            print(f"  [{pct:.1f}%]", end="\r", flush=True)

                print(f"\n✓ Downloaded to {dest_path}")
                return True

            elif resp.status_code == 404:
                print(f"  → Not found (404)")
                continue
            else:
                print(f"  → Error {resp.status_code}: {resp.reason}")
                continue

        except Exception as e:
            print(f"  → Error: {e}")
            continue

    print(f"✗ Failed to download {filename}")
    print(f"  Manual fallback: Visit https://disclosure2.edinet-fsa.go.jp/")
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-api", action="store_true",
                        help="Test EDINET API connectivity")
    parser.add_argument("--period", type=str,
                        choices=['fy2023annual', 'fy2024q1', 'fy2024q2', 'fy2024q3'],
                        help="Download specific period")
    parser.add_argument("--all-recent", action="store_true",
                        help="Download all: FY2023 Annual + FY2024 Q1-Q3")
    parser.add_argument("--dest", type=str, default="/tmp",
                        help="Download destination (default: /tmp)")

    args = parser.parse_args()

    print("=" * 70)
    print("EDINET XBRL Auto-Downloader")
    print("=" * 70)
    print()

    # Load API key
    api_key = get_api_key()
    if not api_key:
        print("✗ EDINET_API_KEY not found in credentials")
        sys.exit(1)

    # Test API
    if args.validate_api:
        if validate_api(api_key):
            print("✓ API is ready to use")
        else:
            print("✗ API connection failed")
            sys.exit(1)
        return

    # Download specific period
    if args.period:
        if download_xbrl_bulk(api_key, args.period, args.dest):
            print(f"\n✓ {args.period} ready in {args.dest}")
        else:
            sys.exit(1)

    # Download all recent periods
    if args.all_recent:
        print("[INFO] Downloading FY2023 + 2024 Q1-Q3 (4 files, ~1.4 GB)")
        print()

        periods = ['fy2023annual', 'fy2024q1', 'fy2024q2', 'fy2024q3']
        success_count = 0

        for period in periods:
            if download_xbrl_bulk(api_key, period, args.dest):
                success_count += 1
            print()

        print("=" * 70)
        print(f"Download Summary: {success_count}/{len(periods)} successful")
        print("=" * 70)

        if success_count == len(periods):
            print("\n✓ All files ready in /tmp")
            print("\nNext: bash scripts/edinet_process_and_archive.sh")
        else:
            print(f"\n⚠ {len(periods) - success_count} file(s) failed")
            print("Manual fallback: https://disclosure2.edinet-fsa.go.jp/")

    if not (args.validate_api or args.period or args.all_recent):
        parser.print_help()


if __name__ == "__main__":
    main()
