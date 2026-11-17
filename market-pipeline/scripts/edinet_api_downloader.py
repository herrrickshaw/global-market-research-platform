#!/usr/bin/env python3
"""
edinet_api_downloader.py — Working EDINET downloader via the official API v2.

Uses the documented API host (api.edinet-fsa.go.jp, NOT the disclosure2 website):
  List:     GET /api/v2/documents.json?date=YYYY-MM-DD&type=2&Subscription-Key=KEY
  Download: GET /api/v2/documents/{docID}?type=1|5&Subscription-Key=KEY
            type=1 → XBRL ZIP, type=5 → pre-extracted CSV ZIP (easier to parse)

EDINET has no bulk endpoint, so this iterates dates, lists filings per day,
filters for listed-company financial reports with XBRL, and downloads each
document individually. A manifest file makes re-runs resumable (skips done).

Doc type codes:
  120 = Annual securities report (有価証券報告書)
  140 = Quarterly report (四半期報告書, abolished from Apr 2024)
  160 = Semi-annual report (半期報告書)

Usage:
  # Smoke test: 1 day, 3 documents
  python3 edinet_api_downloader.py --start 2024-06-28 --end 2024-06-28 --limit 3

  # All annual reports filed in the past year (covers every fiscal year end)
  python3 edinet_api_downloader.py --start 2024-07-01 --end 2025-06-30 --doc-types 120

  # Annual + quarterly + semi-annual, CSV format (smaller, easier to parse)
  python3 edinet_api_downloader.py --start 2024-01-01 --end 2024-12-31 \
      --doc-types 120,140,160 --format csv --dest /tmp/edinet
"""

import argparse
import csv
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

sys.path.insert(0, '/Users/umashankar/market-pipeline/code/python_files')
import env_loader

API_BASE = "https://api.edinet-fsa.go.jp/api/v2"
REQUEST_DELAY = 0.15   # seconds between API calls — be polite
LIST_TYPE = "2"        # documents.json type=2 → include metadata + results
FORMAT_MAP = {"xbrl": "1", "csv": "5"}


def get_api_key() -> str:
    key = env_loader.get('EDINET_API_KEY')
    if not key:
        print("✗ EDINET_API_KEY not found in credentials.env")
        sys.exit(1)
    return key


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def load_manifest(manifest_path: Path) -> dict:
    """docID → row dict of already-downloaded documents."""
    done = {}
    if manifest_path.exists():
        with open(manifest_path, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                done[row['docID']] = row
    return done


def append_manifest(manifest_path: Path, row: dict):
    write_header = not manifest_path.exists()
    with open(manifest_path, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=[
            'docID', 'secCode', 'filerName', 'docTypeCode',
            'periodEnd', 'submitDateTime', 'filename', 'size_bytes'])
        if write_header:
            w.writeheader()
        w.writerow(row)


def list_documents(api_key: str, day: date, session: requests.Session) -> list:
    """List all filings for one date. Returns [] on empty/holiday days."""
    resp = session.get(
        f"{API_BASE}/documents.json",
        params={"date": day.isoformat(), "type": LIST_TYPE, "Subscription-Key": api_key},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    status = data.get('metadata', {}).get('status')
    if str(status) != "200":
        # 404 = no data for that date (weekend/holiday/future) — not an error
        return []
    return data.get('results', [])


def filter_filings(results: list, doc_types: set, listed_only: bool) -> list:
    """Keep listed-company financial reports that carry XBRL."""
    keep = []
    for d in results:
        if d.get('docTypeCode') not in doc_types:
            continue
        if d.get('xbrlFlag') != '1':
            continue
        if listed_only and not d.get('secCode'):
            continue
        if d.get('withdrawalStatus') == '1':   # withdrawn filing
            continue
        keep.append(d)
    return keep


def download_document(api_key: str, doc: dict, fmt_code: str, dest: Path,
                      session: requests.Session, max_retries: int = 3) -> Path | None:
    """Download one document; returns path or None. Validates ZIP magic bytes."""
    doc_id = doc['docID']
    sec = doc.get('secCode') or 'UNLISTED'
    dtype = doc.get('docTypeCode')
    period = (doc.get('periodEnd') or 'noperiod').replace('/', '-')
    out = dest / f"{sec}_{dtype}_{period}_{doc_id}.zip"

    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(
                f"{API_BASE}/documents/{doc_id}",
                params={"type": fmt_code, "Subscription-Key": api_key},
                timeout=120, stream=True,
            )
            if resp.status_code != 200:
                print(f"    ✗ {doc_id}: HTTP {resp.status_code} (attempt {attempt})")
                time.sleep(1.5 * attempt)
                continue

            first = b''
            with open(out, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    if not first:
                        first = chunk[:4]
                    f.write(chunk)

            if not first.startswith(b'PK'):
                # HTML error page instead of ZIP — retry
                out.unlink(missing_ok=True)
                print(f"    ✗ {doc_id}: not a ZIP (attempt {attempt})")
                time.sleep(1.5 * attempt)
                continue

            return out
        except requests.RequestException as e:
            print(f"    ✗ {doc_id}: {e} (attempt {attempt})")
            time.sleep(1.5 * attempt)

    return None


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    p.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    p.add_argument("--doc-types", default="120,140,160",
                   help="Comma-separated docTypeCodes (default: 120,140,160)")
    p.add_argument("--format", choices=["xbrl", "csv"], default="xbrl",
                   help="xbrl = raw XBRL ZIP (type=1), csv = extracted CSV ZIP (type=5)")
    p.add_argument("--dest", default="/tmp/edinet", help="Download directory")
    p.add_argument("--limit", type=int, default=0,
                   help="Stop after N downloads (0 = no limit; use for smoke tests)")
    p.add_argument("--list-only", action="store_true",
                   help="List matching filings without downloading")
    p.add_argument("--include-unlisted", action="store_true",
                   help="Also download filers without a securities code (funds etc.)")
    args = p.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    doc_types = set(t.strip() for t in args.doc_types.split(','))
    fmt_code = FORMAT_MAP[args.format]

    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    manifest_path = dest / "manifest.csv"

    api_key = get_api_key()
    done = load_manifest(manifest_path)
    session = requests.Session()

    print("=" * 70)
    print("EDINET API Downloader (api.edinet-fsa.go.jp v2)")
    print("=" * 70)
    print(f"  Range:     {start} → {end}")
    print(f"  Doc types: {sorted(doc_types)}  Format: {args.format} (type={fmt_code})")
    print(f"  Dest:      {dest}")
    print(f"  Resumable: {len(done)} already in manifest")
    print()

    n_downloaded = n_skipped = n_failed = 0
    total_bytes = 0
    t0 = time.time()

    try:
        for day in daterange(start, end):
            if day.weekday() >= 5:      # skip weekends — no filings
                continue
            try:
                results = list_documents(api_key, day, session)
            except Exception as e:
                print(f"[{day}] list error: {e}")
                continue
            time.sleep(REQUEST_DELAY)

            filings = filter_filings(results, doc_types, not args.include_unlisted)
            if not filings:
                continue

            print(f"[{day}] {len(filings)} matching filings "
                  f"(of {len(results)} total)")

            for doc in filings:
                doc_id = doc['docID']
                if doc_id in done:
                    n_skipped += 1
                    continue

                if args.list_only:
                    print(f"    {doc_id} | {doc.get('secCode')} | "
                          f"{doc.get('docTypeCode')} | {doc.get('filerName', '')[:40]}")
                    continue

                out = download_document(api_key, doc, fmt_code, dest, session)
                time.sleep(REQUEST_DELAY)

                if out is None:
                    n_failed += 1
                    continue

                size = out.stat().st_size
                total_bytes += size
                n_downloaded += 1
                append_manifest(manifest_path, {
                    'docID': doc_id,
                    'secCode': doc.get('secCode') or '',
                    'filerName': doc.get('filerName') or '',
                    'docTypeCode': doc.get('docTypeCode') or '',
                    'periodEnd': doc.get('periodEnd') or '',
                    'submitDateTime': doc.get('submitDateTime') or '',
                    'filename': out.name,
                    'size_bytes': size,
                })
                done[doc_id] = True

                if n_downloaded % 25 == 0:
                    mb = total_bytes / 1e6
                    rate = n_downloaded / max(time.time() - t0, 1) * 60
                    print(f"    … {n_downloaded} files, {mb:.0f} MB, "
                          f"{rate:.0f} files/min")

                if args.limit and n_downloaded >= args.limit:
                    raise KeyboardInterrupt   # clean exit via summary

    except KeyboardInterrupt:
        print("\n[stopped]")

    mins = (time.time() - t0) / 60
    print()
    print("=" * 70)
    print(f"Downloaded: {n_downloaded}  Skipped(done): {n_skipped}  Failed: {n_failed}")
    print(f"Volume: {total_bytes / 1e6:.0f} MB in {mins:.1f} min")
    print(f"Manifest: {manifest_path}")
    print("=" * 70)
    if n_downloaded:
        print(f"\nNext: python3 scripts/edinet_batch_process.py --src {dest}")
        print(f"Then: rclone move {dest} dropbox:/market-data-archive/edinet_xbrl/ "
              f"--include '*.zip'")


if __name__ == "__main__":
    main()
