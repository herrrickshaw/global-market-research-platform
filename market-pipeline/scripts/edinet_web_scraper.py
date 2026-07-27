#!/usr/bin/env python3
"""
edinet_web_scraper.py — Web scraper for EDINET XBRL bulk downloads.

EDINET doesn't expose a direct API for bulk XBRL files, so this scraper
navigates the website to find and download them.

Usage:
  python3 edinet_web_scraper.py --all-recent --dest /tmp
"""

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests


def get_bulk_download_page():
    """Navigate to EDINET bulk download page."""
    print("[INFO] Fetching EDINET bulk download page...")

    url = "https://disclosure2.edinet-fsa.go.jp/weee0040.aspx"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

    try:
        resp = requests.get(url, headers=headers, timeout=10, verify=False)
        if resp.status_code == 200:
            print(f"✓ Page loaded ({len(resp.text)} bytes)")
            return resp.text
        else:
            print(f"✗ Error: {resp.status_code}")
            return None
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def extract_download_links(html: str, period: str = None):
    """
    Extract XBRL bulk download links from the page using regex.

    Pattern matching for files like:
    - EDINET_XBRL_2023_all.zip
    - EDINET_XBRL_2024Q1_all.zip
    """

    print("[INFO] Extracting download links...")

    links = {}

    # Match href="..." with XBRL or EDINET in the path
    # Pattern: <a href="...EDINET_XBRL_...zip"...
    pattern = r'href=["\']([^"\']*(?:EDINET_XBRL|xbrl)[^"\']*\.zip[^"\']*)["\']'

    for match in re.finditer(pattern, html, re.IGNORECASE):
        href = match.group(1)

        # Extract filename from href
        filename_match = re.search(r'(EDINET_XBRL_\d{4}[Qq]?\d?.*?\.zip)', href)
        if filename_match:
            filename = filename_match.group(1)
            full_url = urljoin("https://disclosure2.edinet-fsa.go.jp/", href)
            links[filename] = full_url
            print(f"  Found: {filename}")

    return links


def download_file(url: str, dest_path: Path, max_retries: int = 3) -> bool:
    """Download a file with retry logic."""

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    filename = dest_path.name

    for attempt in range(max_retries):
        try:
            print(f"[INFO] Downloading {filename} (attempt {attempt + 1}/{max_retries})...")

            resp = requests.get(url, headers=headers, timeout=120, stream=True, verify=False)

            if resp.status_code == 200:
                total_size = int(resp.headers.get('content-length', 0))
                downloaded = 0

                with open(dest_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size:
                                pct = (downloaded / total_size * 100)
                                print(f"  [{pct:.1f}%]", end="\r", flush=True)

                size_mb = dest_path.stat().st_size / 1024 / 1024
                print(f"\n✓ Downloaded: {filename} ({size_mb:.1f} MB)")

                # Verify it's a valid ZIP
                if dest_path.stat().st_size < 100:
                    print(f"  ⚠ File too small ({size_mb:.1f} MB) — likely HTML error page")
                    dest_path.unlink()
                    continue

                return True
            else:
                print(f"  ✗ Error: {resp.status_code}")
                continue

        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue

    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-recent", action="store_true",
                        help="Download all recent periods")
    parser.add_argument("--dest", type=str, default="/tmp",
                        help="Download destination")

    args = parser.parse_args()

    print("=" * 70)
    print("EDINET Web Scraper — XBRL Bulk Downloads")
    print("=" * 70)
    print()

    # Step 1: Get page
    html = get_bulk_download_page()
    if not html:
        sys.exit(1)

    print()

    # Step 2: Extract links
    links = extract_download_links(html)
    if not links:
        print("✗ No XBRL links found on page")
        print("  Check: https://disclosure2.edinet-fsa.go.jp/weee0040.aspx")
        sys.exit(1)

    print(f"\n✓ Found {len(links)} XBRL files")
    print()

    # Step 3: Download all or specific
    if args.all_recent:
        dest_path = Path(args.dest)
        success_count = 0

        for filename, url in sorted(links.items()):
            file_path = dest_path / filename
            if download_file(url, file_path):
                success_count += 1
            print()

        print("=" * 70)
        print(f"Download Summary: {success_count}/{len(links)} successful")
        print("=" * 70)

        if success_count == len(links):
            print(f"\n✓ All files ready in {args.dest}")
            print("\nNext: bash scripts/edinet_process_and_archive.sh")
        else:
            print(f"\n⚠ {len(links) - success_count} file(s) failed")

    else:
        # Just list available files
        print("Available files:")
        for filename in sorted(links.keys()):
            print(f"  - {filename}")


if __name__ == "__main__":
    main()
