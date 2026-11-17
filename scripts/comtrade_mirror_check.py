#!/usr/bin/env python3
"""Mirror check: what exporters report shipping to India vs what India reports importing from them.

For HS6 284610/284690, partners Korea, Japan, China, France, 2019-2024, via the keyless Comtrade
preview API (COMTRADE_API_KEY switches to the full API). Output: ~/Downloads/comtrade_mirror_check_v1.csv
Large gaps mean partner attribution (origin vs destination) or HS classification differs between the
two customs services; they are a reason not to trust a single-sided supplier ranking.
"""
import csv, os, time
import requests

KEY = os.environ.get("COMTRADE_API_KEY")
BASE = "https://comtradeapi.un.org/data/v1/get/C/A/HS" if KEY else "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
INDIA = 699
PARTNERS = {"Korea": 410, "Japan": 392, "China": 156, "France": 251}


def get(**p):
    hdr = {"Ocp-Apim-Subscription-Key": KEY} if KEY else {}
    for n in range(4):
        r = requests.get(BASE, params=dict(partner2Code=0, customsCode="C00", motCode=0, **p), headers=hdr, timeout=60)
        if r.status_code == 200:
            rows = r.json().get("data") or []
            return rows[0] if rows else None
        time.sleep(5 * (n + 1))
    raise RuntimeError(p)


def cols(r):
    if not r:
        return "", ""
    kg = r.get("netWgt") or 0
    return round(r["primaryValue"]), round(kg)


out = []
for code in ("284610", "284690"):
    for name, pc in PARTNERS.items():
        for yr in range(2019, 2025):
            a = get(reporterCode=pc, partnerCode=INDIA, period=yr, cmdCode=code, flowCode="X"); time.sleep(1.2)
            b = get(reporterCode=INDIA, partnerCode=pc, period=yr, cmdCode=code, flowCode="M"); time.sleep(1.2)
            av, ak = cols(a); bv, bk = cols(b)
            out.append(dict(hs6=code, year=yr, partner=name, exporter_value_usd=av, exporter_kg=ak, india_value_usd=bv, india_kg=bk))
        print(code, name, "done", flush=True)
fn = os.path.expanduser("~/Downloads/comtrade_mirror_check_v1.csv")
w = csv.DictWriter(open(fn, "w", newline=""), fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
print("wrote", fn, len(out), "rows")
