#!/usr/bin/env python3
"""
dart_api_downloader.py — Korea fundamentals via the official DART API (opendart.fss.or.kr).

Korea's EDGAR-equivalent (Financial Supervisory Service). Mirrors the EDINET
playbook, but simpler: DART serves structured financial statements as JSON —
no filing ZIPs or XBRL parsing needed.

Endpoints:
  corpCode.xml         corp_code ↔ stock_code map (ZIP of XML, all filers)
  fnlttSinglAcntAll    all statement accounts, one company × year × report

Quota: 20,000 requests/day per key. Annual reports (reprt_code=11011);
consolidated (CFS) preferred, separate (OFS) fallback.

Usage:
  python3 dart_api_downloader.py --years 2022,2023,2024,2025 --dest /tmp/dart_kr
  python3 dart_api_downloader.py --years 2024 --limit 5 --dest /tmp/dart_test  # smoke
"""

import argparse
import csv
import io
import json
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, '/Users/umashankar/market-pipeline/code/python_files')
import env_loader

API = "https://opendart.fss.or.kr/api"
DELAY = 0.1  # ~10 req/s, well under quota pace

# account_nm (Korean) / account_id (IFRS) → canonical field
ACCOUNT_MAP = {
    'revenue': {'ids': ['ifrs-full_Revenue'], 'names': ['매출액', '수익(매출액)', '영업수익']},
    'operating_income': {'ids': ['dart_OperatingIncomeLoss'], 'names': ['영업이익', '영업이익(손실)']},
    'net_income': {'ids': ['ifrs-full_ProfitLoss'], 'names': ['당기순이익', '당기순이익(손실)']},
    'total_assets': {'ids': ['ifrs-full_Assets'], 'names': ['자산총계']},
    'total_liabilities': {'ids': ['ifrs-full_Liabilities'], 'names': ['부채총계']},
    'equity': {'ids': ['ifrs-full_Equity'], 'names': ['자본총계']},
    'cfo': {'ids': ['ifrs-full_CashFlowsFromUsedInOperatingActivities'],
            'names': ['영업활동현금흐름', '영업활동으로인한현금흐름']},
}


def get_key() -> str:
    key = env_loader.get('DART_KEY')
    if not key:
        print("✗ DART_KEY not found"); sys.exit(1)
    return key


def fetch_corp_codes(key: str, dest: Path) -> dict:
    """Download corp_code map; return {stock_code: (corp_code, corp_name)}."""
    cache = dest / 'corp_codes.json'
    if cache.exists():
        return json.loads(cache.read_text(encoding='utf-8'))
    print("[INFO] Downloading corpCode.xml …")
    r = requests.get(f"{API}/corpCode.xml", params={'crtfc_key': key}, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        xml = z.read(z.namelist()[0])
    root = ET.fromstring(xml)
    m = {}
    for el in root.iter('list'):
        stock = (el.findtext('stock_code') or '').strip()
        if stock:  # listed companies only
            m[stock] = (el.findtext('corp_code'), el.findtext('corp_name'))
    cache.write_text(json.dumps(m, ensure_ascii=False), encoding='utf-8')
    print(f"✓ {len(m)} listed companies in corp map")
    return m


def parse_accounts(items: list) -> dict:
    """Map DART account rows → canonical fields.

    fs_div (CFS/OFS) is a request parameter, not a response field — the caller
    makes separate CFS and OFS requests, so just scan the rows given.
    """
    out = {}
    for field, spec in ACCOUNT_MAP.items():
        for r in items:
            if r.get('account_id') in spec['ids'] or r.get('account_nm') in spec['names']:
                amt = (r.get('thstrm_amount') or '').replace(',', '').strip()
                if amt and amt not in ('-',):
                    try:
                        out[field] = int(amt)
                        break
                    except ValueError:
                        pass
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--years', default='2022,2023,2024,2025')
    p.add_argument('--dest', default='/tmp/dart_kr')
    p.add_argument('--limit', type=int, default=0, help='company limit (smoke test)')
    args = p.parse_args()

    years = [y.strip() for y in args.years.split(',')]
    dest = Path(args.dest); dest.mkdir(parents=True, exist_ok=True)
    key = get_key()
    corp = fetch_corp_codes(key, dest)

    manifest_path = dest / 'manifest.csv'
    done = set()
    if manifest_path.exists():
        with open(manifest_path, newline='', encoding='utf-8') as f:
            done = {(r['stock_code'], r['year']) for r in csv.DictReader(f)}

    out_path = dest / 'dart_fundamentals.jsonl'
    raw_dir = dest  # jsonl is both data and raw archive (responses are parsed inline)

    stocks = sorted(corp.keys())
    if args.limit:
        stocks = stocks[:args.limit]

    total = len(stocks) * len(years)
    print(f"[INFO] {len(stocks)} companies × {len(years)} years = {total} requests "
          f"(done: {len(done)})")

    n_ok = n_nodata = n_err = 0
    t0 = time.time()
    session = requests.Session()

    with open(out_path, 'a', encoding='utf-8') as outf, \
         open(manifest_path, 'a', newline='', encoding='utf-8') as manf:
        mw = csv.DictWriter(manf, fieldnames=['stock_code', 'year', 'status'])
        if not done and manf.tell() == 0:
            mw.writeheader()

        for stock in stocks:
            corp_code, corp_name = corp[stock]
            for year in years:
                if (stock, year) in done:
                    continue
                try:
                    r = session.get(f"{API}/fnlttSinglAcntAll.json", params={
                        'crtfc_key': key, 'corp_code': corp_code,
                        'bsns_year': year, 'reprt_code': '11011', 'fs_div': 'CFS',
                    }, timeout=30)
                    d = r.json()
                    status = d.get('status')
                    if status == '000':
                        acc = parse_accounts(d.get('list', []))
                        if not acc:  # CFS empty → try OFS
                            r2 = session.get(f"{API}/fnlttSinglAcntAll.json", params={
                                'crtfc_key': key, 'corp_code': corp_code,
                                'bsns_year': year, 'reprt_code': '11011', 'fs_div': 'OFS',
                            }, timeout=30)
                            d2 = r2.json()
                            if d2.get('status') == '000':
                                acc = parse_accounts(d2.get('list', []))
                            time.sleep(DELAY)
                        if acc:
                            rec = {'stock_code': stock, 'corp_name': corp_name,
                                   'bsns_year': year, **acc}
                            outf.write(json.dumps(rec, ensure_ascii=False) + '\n')
                            n_ok += 1
                            mw.writerow({'stock_code': stock, 'year': year, 'status': 'ok'})
                        else:
                            n_nodata += 1
                            mw.writerow({'stock_code': stock, 'year': year, 'status': 'noacct'})
                    elif status == '013':  # no data
                        n_nodata += 1
                        mw.writerow({'stock_code': stock, 'year': year, 'status': 'nodata'})
                    elif status == '020':  # quota exceeded
                        print("\n✗ Daily quota exceeded — resume tomorrow (manifest saved)")
                        return
                    else:
                        n_err += 1
                        mw.writerow({'stock_code': stock, 'year': year, 'status': f'err{status}'})
                except Exception as e:
                    n_err += 1
                    mw.writerow({'stock_code': stock, 'year': year, 'status': 'exc'})
                time.sleep(DELAY)

                nd = n_ok + n_nodata + n_err
                if nd % 200 == 0 and nd:
                    rate = nd / max(time.time() - t0, 1) * 60
                    print(f"  … {nd} done ({n_ok} ok / {n_nodata} nodata / {n_err} err) "
                          f"{rate:.0f}/min", flush=True)

    print(f"\n{'='*60}\nDone: {n_ok} ok, {n_nodata} no-data, {n_err} errors "
          f"in {(time.time()-t0)/60:.1f} min\nOutput: {out_path}\n{'='*60}")
    print(f"Next: /usr/bin/python3 scripts/korea_aggregate_all.py")


if __name__ == '__main__':
    main()
