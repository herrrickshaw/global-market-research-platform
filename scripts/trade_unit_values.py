#!/usr/bin/env python3
"""Unit values (USD/kg) for ceria / diamond / abrasive HS codes from raw DGCI&S TradeStat files.

Inputs: ~/Downloads/trade data/TradeStat-Eidb-{Import,Export}-Commodity-wise*.xlsx
  - files whose 2nd line says "Values in US $ Million" hold value
  - files whose 2nd line says "Values in Quantity" hold quantity (unit in column 'Unit')
Overlapping windows are de-duplicated per (flow, HS8, FY, measure); if two files disagree
the later-generated file wins and the conflict is reported.

Output: one CSV row per (flow, HS8, FY) with value, quantity, unit and unit value.
  python3 scripts/trade_unit_values.py [-o out.csv]
"""
import argparse, csv, glob, os, re
import openpyxl

SRC = os.path.expanduser("~/Downloads/trade data")
PREFIXES = ("2805", "2846", "7102", "7104", "7105", "6804", "6805", "3405", "2818", "2849")
TO_KG = {"KGS": 1.0, "TON": 1000.0, "TNE": 1000.0, "GMS": 0.001, "GRM": 0.001,
         "CTM": 0.0002, "CRT": 0.0002}  # unit -> kg (CTM/CRT = metric carat = 0.2 g)
YEAR = re.compile(r"^\d{4}\s*-\s*\d{4}$")


def read(path):
    ws = openpyxl.load_workbook(path, read_only=True).active
    rows = ws.iter_rows(values_only=True)
    title = next(rows)[0]
    meta = next(rows)[0]
    hdr = next(rows)
    flow = "import" if "Import" in title else "export"
    measure = "qty" if "Quantity" in meta else "value"
    ycols = {i: re.sub(r"\s", "", h) for i, h in enumerate(hdr) if isinstance(h, str) and YEAR.match(h.strip())}
    unit_i = hdr.index("Unit") if "Unit" in hdr else None
    for r in rows:
        if len(r) < 3:
            continue
        code = str(r[1] or "")
        if code[:4] not in PREFIXES:
            continue
        for i, fy in ycols.items():
            v = r[i] if i < len(r) else None
            if isinstance(v, (int, float)):
                yield flow, code, r[2], (r[unit_i] if unit_i is not None and unit_i < len(r) else None), fy, measure, float(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", default=os.path.expanduser("~/Downloads/trade_unit_values_v1.csv"))
    a = ap.parse_args()

    data, names, units, conflicts = {}, {}, {}, []
    files = sorted(glob.glob(os.path.join(SRC, "TradeStat-Eidb-*-Commodity-wise*.xlsx")), key=os.path.getmtime)
    for f in files:
        for flow, code, name, unit, fy, measure, v in read(f):
            k = (flow, code, fy, measure)
            if k in data and abs(data[k] - v) > 1e-9:
                conflicts.append((os.path.basename(f), k, data[k], v))
            data[k] = v
            names[code] = name
            if unit:
                units[(flow, code)] = unit.strip().upper()

    keys = sorted({(fl, c, fy) for fl, c, fy, _ in data})
    n = 0
    with open(a.o, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["flow", "hs8", "commodity", "fy", "value_usd_m", "qty", "unit", "unit_value_usd_per_kg", "low_precision"])
        for fl, c, fy in keys:
            val, qty, unit = data.get((fl, c, fy, "value")), data.get((fl, c, fy, "qty")), units.get((fl, c))
            uv = ""
            if val and qty and unit in TO_KG and qty > 0:
                uv = round(val * 1e6 / (qty * TO_KG[unit]), 2)
            # TradeStat rounds value to US$0.01M: below US$0.1M the price can be off by >5%
            w.writerow([fl, c, names[c], fy, val, qty, unit, uv, "Y" if val is not None and val < 0.1 else ""])
            n += 1
    print(f"{len(files)} files, {n} rows -> {a.o}; {len(conflicts)} value conflicts between overlapping files")
    for c in conflicts[:10]:
        print("  CONFLICT", c)


if __name__ == "__main__":
    main()
