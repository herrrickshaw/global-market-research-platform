"""
Build the cross-repo requirements sheet.

Aggregates every requirements*.txt across the doc/PDF-parsing repos into
  docs/requirements_sheet.csv   (repo, file, requirement, package, context)
  docs/requirements-all.txt     (deduped union, pip-installable)
Run after adding/changing any requirements file:  python3 scripts/build_requirements_sheet.py
"""
import csv, re, pathlib

home = pathlib.Path.home()
REQ_FILES = [
    home / 'requirements.txt',
    home / 'backend' / 'requirements.txt',
    home / 'requirements_nse_bse.txt',
    home / 'market-pipeline' / 'requirements-ocr.txt',
    home / 'ppac-ready-reckoner-data' / 'requirements-ocr.txt',
    home / 'BazaarTalks' / 'requirements-ocr.txt',
    home / 'india-trade-sector-policy-recommendations' / 'requirements-ocr.txt',
    home / 'repos' / 'cng-cgd-retail-outlet-mapping' / 'requirements-ocr.txt',
    home / 'repos' / 'global-market-data' / 'requirements-ocr.txt',
    home / 'repos' / 'global-market-scanners' / 'requirements-ocr.txt',
    home / 'repos' / 'global-stock-screener' / 'requirements-ocr.txt',
    home / 'vehicle_fuel_mileage' / 'requirements-ocr.txt',
]

def repo_of(f: pathlib.Path) -> str:
    rel = f.relative_to(home).parts
    return rel[0] if rel[0] not in ('requirements.txt', 'requirements_nse_bse.txt', 'backend') else 'HOME'

rows, seen = [], {}
for f in REQ_FILES:
    if not f.exists():
        continue
    comment = ''
    for line in f.read_text().splitlines():
        s = line.strip()
        if not s:
            comment = ''
            continue
        if s.startswith('#'):
            c = s.lstrip('# -').strip()
            if c and 'pip install' not in c:
                comment = c
            continue
        pkg = re.split(r'[<>=!\[ ;]', s)[0]
        rows.append({'repo': repo_of(f), 'file': str(f.relative_to(home)),
                     'requirement': s, 'package': pkg, 'context': comment})
        seen.setdefault(pkg.lower(), s)

out = home / 'docs'
out.mkdir(exist_ok=True)
with open(out / 'requirements_sheet.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=['repo', 'file', 'requirement', 'package', 'context'])
    w.writeheader()
    w.writerows(rows)
(out / 'requirements-all.txt').write_text(
    '# Auto-generated union of every requirements*.txt across repos (deduped by package).\n'
    '# Regenerate: python3 scripts/build_requirements_sheet.py\n'
    + '\n'.join(sorted(seen.values(), key=str.lower)) + '\n')
print(f'{len(rows)} rows, {len(seen)} unique packages')
