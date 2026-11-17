#!/usr/bin/env python3
"""Supplier concentration for ceria / rare-earth / diamond-powder HS6 codes from UN Comtrade.

Two views per HS6 and year:
  india_imports  India (reporter 699) imports by partner   -> who supplies India, at what USD/kg
  world_exports  every reporter's total exports (partner 0) -> how concentrated global supply is

Uses the keyless public preview API (max 500 rows per call, HS6, annual). If COMTRADE_API_KEY is
set (free key from comtradedeveloper.un.org) it uses the full data API instead.

  python3 scripts/comtrade_supplier_concentration.py [--years 2019-2024] [--codes 284610,284690]
Outputs (in ~/Downloads): comtrade_india_import_partners_v1.csv, comtrade_concentration_v1.csv
"""
import argparse, csv, os, sys, time
import requests

CODES = {"284610": "Cerium compounds", "284690": "Other rare-earth compounds", "280530": "Rare-earth metals",
         "710510": "Diamond dust & powder", "710590": "Dust & powder of other precious stones"}
INDIA, WORLD = 699, 0
KEY = os.environ.get("COMTRADE_API_KEY")
BASE = ("https://comtradeapi.un.org/data/v1/get/C/A/HS" if KEY else "https://comtradeapi.un.org/public/v1/preview/C/A/HS")
REF = "https://comtradeapi.un.org/files/v1/app/reference/{}.json"


def get(params, tries=4):
    hdr = {"Ocp-Apim-Subscription-Key": KEY} if KEY else {}
    for n in range(tries):
        r = requests.get(BASE, params=params, headers=hdr, timeout=60)
        if r.status_code == 200:
            rows = r.json().get("data") or []
            if len(rows) >= 500 and not KEY:
                print(f"  WARNING: {params} hit the 500-row preview cap; result truncated", file=sys.stderr)
            return rows
        if r.status_code in (429, 500, 502, 503):
            time.sleep(5 * (n + 1))
            continue
        r.raise_for_status()
    raise RuntimeError(f"Comtrade failed after {tries} tries: {params}")


def names(kind, idkey, namekey):
    res = requests.get(REF.format(kind), timeout=60).json()["results"]
    return {int(x[idkey]): x[namekey] for x in res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2019-2024")
    ap.add_argument("--codes", default=",".join(CODES))
    a = ap.parse_args()
    y0, y1 = map(int, a.years.split("-"))
    partner = names("partnerAreas", "PartnerCode", "PartnerDesc")
    reporter = names("Reporters", "reporterCode", "reporterDesc")
    dl = os.path.expanduser("~/Downloads")

    common = dict(partner2Code=0, customsCode="C00", motCode=0)
    detail, conc = [], []
    for code in a.codes.split(","):
        for yr in range(y0, y1 + 1):
            for scope, params, who, wkey, wname in (
                ("india_imports", dict(reporterCode=INDIA, partnerCode="", flowCode="M"), "partnerCode", partner, "partner"),
                ("world_exports", dict(partnerCode=WORLD, flowCode="X"), "reporterCode", reporter, "exporter"),
            ):
                rows = get(dict(period=yr, cmdCode=code, **params, **common))
                time.sleep(1.2)
                # drop the World aggregate (india_imports) and rows without a value
                rows = [r for r in rows if r.get(who) not in (WORLD, None) and (r.get("primaryValue") or 0) > 0]
                if not rows:
                    continue
                tot = sum(r["primaryValue"] for r in rows)
                rows.sort(key=lambda r: -r["primaryValue"])
                shares = [r["primaryValue"] / tot for r in rows]
                conc.append(dict(scope=scope, hs6=code, commodity=CODES.get(code, ""), year=yr, total_usd=round(tot),
                                 n_parties=len(rows), top1=wkey.get(rows[0][who], rows[0][who]), top1_share=round(shares[0], 3),
                                 top3_share=round(sum(shares[:3]), 3), hhi=round(sum(s * s for s in shares) * 10000)))
                if scope == "india_imports":
                    for r, s in zip(rows, shares):
                        kg = r.get("netWgt") or 0
                        detail.append(dict(hs6=code, year=yr, partner_code=r[who], partner=wkey.get(r[who], r[who]),
                                           value_usd=round(r["primaryValue"]), net_wgt_kg=round(kg) if kg else "",
                                           usd_per_kg=round(r["primaryValue"] / kg, 2) if kg else "", share=round(s, 3)))
            print(code, yr, "done", flush=True)

    for fn, data in (("comtrade_india_import_partners_v1.csv", detail), ("comtrade_concentration_v1.csv", conc)):
        with open(os.path.join(dl, fn), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
        print("wrote", os.path.join(dl, fn), len(data), "rows")


if __name__ == "__main__":
    main()
