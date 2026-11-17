"""Build the global petroleum trade + US storage dashboard from collected data."""
import json, os, sys, html
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from charts import area_chart, multi_line, bar_chart, fmt_short, fmt_bn
import partners   # preview API returns partnerDesc=null; names come from the reference file

def load(name, default=None):
    p = os.path.join(HERE, name)
    if not os.path.exists(p): return default
    with open(p) as f: return json.load(f)

eia = load("eia_series.json", {})
# Key-gated additions from the EIA v2 API (scripts/eia_opec.py). Absent until a key
# is configured; the workbook series above remain the fallback either way.
_api_path = os.path.expanduser("~/scripts/data/eia_api_series.json")
eia_api = json.load(open(_api_path)) if os.path.exists(_api_path) else {}
prod = load("products_world.json", {})
pair = load("pairings2.json", {})
ychoice = load("year_choice.json", {})
TS = json.load(open("/Users/umashankar/india-trade-data-analysis/data/"
                    "tradestat_hsn_export_import_2018-19_to_2025-26.json"))

PRODNAME = {
 "2709": "Crude oil", "271012": "Gasoline / light oils",
 "271019": "Diesel, jet, fuel oil + base oils", "271020": "Biodiesel blends",
 "271111": "LNG", "271112": "Propane", "271113": "Butanes", "271119": "Other LPG",
 "271121": "Natural gas (gaseous)", "2712": "Petroleum jelly / waxes",
 "2713": "Petroleum coke / bitumen", "2715": "Bituminous mixtures",
 "3403": "Lubricating preparations",
}

# ---------- topic 1: US storage & reserves ----------
def series(k):
    s = eia.get(k)
    return s["points"] if s else []

def thin(pts, keep=420):
    if len(pts) <= keep: return pts
    step = len(pts) / keep
    out = [pts[int(i * step)] for i in range(keep)]
    if out[-1] != pts[-1]: out.append(pts[-1])
    return out

comm = thin(series("WCESTUS1")); spr = thin(series("WCSSTUS1"))
tot  = thin(series("WCRSTUS1")); cush = thin(series("W_EPC0_SAX_YCUOK_MBBL"))
prov = [p for p in series("RCRR01NUS_1") if p[1] > 0]

def stat(pts):
    if not pts: return None
    ys = [v for _, v in pts]
    mx = max(pts, key=lambda r: r[1]); mn = min(pts, key=lambda r: r[1])
    return {"last": pts[-1], "max": mx, "min": mn, "pct_of_max": 100 * pts[-1][1] / mx[1]}

S = {k: stat(series(k)) for k in
     ["WCESTUS1", "WCSSTUS1", "WCRSTUS1", "W_EPC0_SAX_YCUOK_MBBL", "WTTSTUS1", "RCRR01NUS_1"]}

def mb(v): return f"{v/1000:,.1f}"   # thousand bbl -> million bbl

tiles = []
for key, label, note in [
    ("W_EPC0_SAX_YCUOK_MBBL", "Cushing, OK", "WTI delivery hub"),
    ("WCSSTUS1", "Strategic Petroleum Reserve", "federal buffer"),
    ("WCESTUS1", "Commercial crude (ex-SPR)", "industry working stock"),
    ("WCRSTUS1", "Total crude incl. SPR", "all US crude"),
]:
    s = S[key]
    if not s: continue
    pct = s["pct_of_max"]
    sev = "crit" if pct < 45 else ("warn" if pct < 70 else "good")
    tiles.append(f"""<div class="tile">
  <div class="tile-h">{label}<span class="pill {sev}">{pct:.0f}% of peak</span></div>
  <div class="tile-v">{mb(s['last'][1])}<span class="u">M bbl</span></div>
  <div class="tile-n">{note} · peak {mb(s['max'][1])}M ({s['max'][0][:7]})</div>
</div>""")

# ---------- topic 2: crude mix evidence ----------
usa = prod.get("USA", {}).get("products", {})
def pv(code, flow):
    return (usa.get(code, {}) or {}).get(flow) or 0
crude_x, crude_m = pv("2709", "X"), pv("2709", "M")

# unit values by partner from pairings (grade proxy)
uv_rows = []
if pair.get("USA"):
    rows = pair["USA"]["products"].get("2709", {}).get("rows", [])
    agg = {}
    for r in rows:
        if not r.get("netWgt") or not r.get("value"): continue
        if partners.is_group(r["pc"]): continue
        k = (r["flow"], partners.name(r["pc"]))
        a = agg.setdefault(k, [0, 0])
        a[0] += r["value"]; a[1] += r["netWgt"]
    for (flow, p), (v, w) in agg.items():
        if w > 5e8:   # >500k tonnes, keeps it to material partners
            uv_rows.append((flow, p, v / (w / 1000.0), v))
    uv_rows.sort(key=lambda r: -r[3])

def uv_table(flow, title):
    rs = [r for r in uv_rows if r[0] == flow][:8]
    if not rs: return ""
    body = "".join(
        f"<tr><td>{html.escape(str(p))}</td><td class='n'>{v/1e9:,.2f}</td>"
        f"<td class='n'>{u:,.0f}</td></tr>" for _, p, u, v in rs)
    return f"""<div class="tbl-wrap"><table><caption>{title}</caption>
<thead><tr><th>Partner</th><th class="n">US$ bn</th><th class="n">US$/tonne</th></tr></thead>
<tbody>{body}</tbody></table></div>"""

# ---------- topic 3: country petroleum profiles ----------
prof_rows, basis_rows = [], []
for name, v in prod.items():
    if name == "India": continue
    ps = v.get("products", {})
    yr = v.get("year")
    sumX = sum((p.get("X") or 0) for p in ps.values())
    sumM = sum((p.get("M") or 0) for p in ps.values())
    ch = (ychoice.get(name, {}).get("years", {}) or {}).get(str(yr)) \
         or (ychoice.get(name, {}).get("years", {}) or {}).get(yr) or {}
    chX, chM = ch.get("X", 0) or 0, ch.get("M", 0) or 0
    # Neither level is universally reliable: Qatar/India lose HS-6 detail, Mexico/Oman
    # lose the chapter aggregate. Take the larger of the two as the scale estimate.
    X, M = max(sumX, chX), max(sumM, chM)
    if X == 0 and M == 0:
        basis_rows.append((name, yr, "no chapter-27 data reported", "—")); continue
    src = []
    if chX > sumX * 1.4: src.append("chapter total (HS-6 detail incomplete)")
    elif sumX > chX * 1.4: src.append("HS-6 sum (chapter aggregate unreliable)")
    else: src.append("both levels agree")
    prof_rows.append((f"{name} ({yr})", X - M))
    basis_rows.append((name, yr, src[0], f"{X/1e9:,.1f} / {M/1e9:,.1f}"))
# India: chapter-27 total is sound and matches DGCI&S, but HS-6 import detail is missing
ind_x = TS["by_chapter"]["export"]["27"]["2025 - 2026"] * 1e6
ind_m = TS["by_chapter"]["import"]["27"]["2025 - 2026"] * 1e6
prof_rows.append(("India (FY25-26, TRADESTAT)", ind_x - ind_m))
basis_rows.append(("India", "FY25-26", "DGCI&S TRADESTAT (Comtrade HS-6 imports missing)",
                   f"{ind_x/1e9:,.1f} / {ind_m/1e9:,.1f}"))
prof_rows.sort(key=lambda r: -r[1])

# US product-level net
us_prod_rows = []
for c, p in usa.items():
    net = (p.get("X") or 0) - (p.get("M") or 0)
    us_prod_rows.append((PRODNAME.get(c, c), net))
us_prod_rows.sort(key=lambda r: -r[1])

# ---------- topic 4: pairings ----------
NONDISC_EXACT = {"Areas, nes", "Bunkers", "Free Zones", "Special Categories",
                 "Other Asia, nes", "Other Europe, nes", "Other Africa, nes",
                 "Other America, nes", "Oceania, nes", "Europe EU, nes",
                 "Rest of America, nes", "Asia, nes", "Africa CAMEU region, nes"}

def nondisclosed(pc):
    """Residual 'not elsewhere specified' buckets are NOT counterparties. Several GCC
    reporters book most exports here, so counting them as partners invents trade."""
    nm = partners.name(pc)
    return nm in NONDISC_EXACT or nm.endswith(", nes") or partners.is_group(pc)


def flow_agg(reporter, code, flow):
    d = pair.get(reporter)
    if not d: return {}, 0.0, 0.0
    named, hidden = {}, 0.0
    for r in d["products"].get(code, {}).get("rows", []):
        if r["flow"] != flow: continue
        v = r["value"] or 0
        if nondisclosed(r["pc"]): hidden += v
        else: named[partners.name(r["pc"])] = named.get(partners.name(r["pc"]), 0) + v
    return named, sum(named.values()), hidden


def top_pairs(reporter, code, flow, n=6):
    named, _, _ = flow_agg(reporter, code, flow)
    return [(k, v) for k, v in sorted(named.items(), key=lambda kv: -kv[1])[:n] if v > 0]


def disclosure(reporter, code, flow):
    _, shown, hidden = flow_agg(reporter, code, flow)
    tot = shown + hidden
    return (100 * shown / tot) if tot else None, hidden


# per-reporter export destination disclosure across the focus products
DISC_ROWS = []
for rep in ["USA", "Mexico", "Saudi Arabia", "UAE", "Qatar", "Kuwait", "Oman", "India"]:
    if rep not in pair: continue
    shown = hidden = 0.0
    for code in ["2709", "271012", "271019", "271112", "271113", "3403"]:
        _, s, h = flow_agg(rep, code, "X"); shown += s; hidden += h
    tot = shown + hidden
    if tot > 0:
        DISC_ROWS.append((rep, pair[rep]["year"], 100 * shown / tot, hidden / 1e9, tot / 1e9))
DISC_ROWS.sort(key=lambda r: r[2])


# ---------- mirror-derived pairings: who the importers say they buy from ----------
MIRROR_SRC = ["USA", "India", "Mexico"]
def mirror_suppliers(code, n=8):
    agg = {}
    for imp in MIRROR_SRC:
        named, _, _ = flow_agg(imp, code, "M")
        for src, v in named.items():
            d = agg.setdefault(src, {})
            d[imp] = d.get(imp, 0) + v
    tot = {k: sum(v.values()) for k, v in agg.items()}
    return [(k, agg[k], tot[k]) for k in sorted(tot, key=lambda x: -tot[x])[:n]]


def pair_value(reporter, code, flow, partner_name):
    d = pair.get(reporter)
    if not d: return 0.0
    return sum(r["value"] or 0 for r in d["products"].get(code, {}).get("rows", [])
               if r["flow"] == flow and partners.name(r["pc"]) == partner_name)


# ---------- mirror discrepancy: US-declared exports vs partner-declared imports ----------
MIRROR = []
for code, label in [("271012", "Gasoline / light oils"), ("271019", "Diesel, jet, fuel oil"),
                    ("271112", "Propane"), ("3403", "Lubricating preparations"),
                    ("2713", "Petroleum coke / bitumen")]:
    us_side = pair_value("USA", code, "X", "Mexico")
    mx_side = ((prod.get("Mexico", {}).get("products", {}).get(code, {}) or {}).get("M")) or 0
    if us_side > 0 or mx_side > 0:
        ratio = (mx_side / us_side) if us_side > 0 else None
        MIRROR.append((label, code, us_side, mx_side, ratio))

CAPPED = [(rep, code, PRODNAME.get(code, code))
          for rep, d in pair.items()
          for code, pd_ in d.get("products", {}).items()
          if pd_.get("status") == "capped"]

PAIR_FOCUS = [("2709", "Crude oil"), ("271012", "Gasoline / light oils"),
              ("271019", "Diesel, jet, fuel oil + base oils"),
              ("271112", "Propane"), ("271113", "Butanes"), ("3403", "Lubricating preparations")]

pair_sections = []
for rep in ["USA", "Mexico", "Saudi Arabia", "UAE", "Qatar", "Kuwait", "Oman", "Bahrain"]:
    d = pair.get(rep)
    if not d: continue
    blocks = []
    for code, label in PAIR_FOCUS:
        xs = top_pairs(rep, code, "X"); ms = top_pairs(rep, code, "M")
        if not xs and not ms: continue
        def lst(items, kind):
            if not items: return f"<div class='none'>no {kind} recorded</div>"
            return "".join(
                f"<div class='pr'><span class='pn'>{html.escape(str(p))}</span>"
                f"<span class='pv'>{v/1e9:,.2f}</span></div>" for p, v in items)
        blocks.append(f"""<div class="pairbox">
  <h4>{label} <span class="hs">HS {code}</span></h4>
  <div class="pcols">
    <div><div class="plab out">Sells to</div>{lst(xs,'exports')}</div>
    <div><div class="plab in">Buys from</div>{lst(ms,'imports')}</div>
  </div></div>""")
    if blocks:
        pair_sections.append(f"""<div class="repblock">
  <h3>{rep} <span class="yr">{d['year']}</span></h3>
  <div class="pairgrid">{''.join(blocks)}</div></div>""")

# ---------- key-gated OPEC section ----------
FORECAST_FROM = "2026-08"   # STEO carries projections past the current month

def find_break(pts, since="2023-01", min_jump=3.0):
    """Largest month-on-month move; a simultaneous jump across independent series
    means the aggregate was redefined, not that production moved."""
    p = [x for x in pts if x[0] >= since]
    if len(p) < 3: return None
    mv = max(((p[i][1] - p[i - 1][1], p[i][0]) for i in range(1, len(p))),
             key=lambda t: abs(t[0]))
    return mv if abs(mv[0]) >= min_jump else None


def opec_block():
    if not eia_api: return ""
    op = (eia_api.get("opec_production") or {}).get("series") or {}
    if not op: return ""

    charts, notes, breaks = [], [], []
    for sid in ["COPR_OPEC", "PAPR_OPEC", "COPS_SA"]:
        s = op.get(sid) or {}
        if s.get("error"):
            notes.append(f"{sid}: {s['error']}"); continue
        pts = s.get("points") or []
        if not pts: continue
        hist = [x for x in pts if x[0] < FORECAST_FROM]
        fcst = [x for x in pts if x[0] >= FORECAST_FROM]
        brk = find_break(hist, min_jump=(0.9 if sid == "COPS_SA" else 3.0))
        pre = [x for x in hist if not brk or x[0] < brk[1]]
        post = [x for x in hist if brk and x[0] >= brk[1]]
        if brk:
            breaks.append((sid, brk[1], brk[0], len(post)))
        charts.append(f"""<div class="panel">
  <h3>{html.escape(str(s.get('name') or sid))} <span class="hs">{sid}</span></h3>
  {area_chart(pre, accent='var(--teal)', fill='rgba(30,107,107,.13)',
              unit=str(s.get('unit') or ''))}
  <div class="cap">EIA STEO · {html.escape(str(s.get('unit') or ''))} ·
  plotted {pre[0][0]}–{pre[-1][0]} ({len(pre)} months).
  {f"Series redefined at {brk[1]} ({brk[0]:+.2f}); the {len(post)} months after it are on a different basis and are excluded from this line." if brk else ""}
  {f"{len(fcst)} forecast months to {fcst[-1][0]} also excluded." if fcst else ""}</div>
</div>""")

    pr = eia_api.get("proved_reserves") or {}
    res_note = ""
    if pr.get("points"):
        api_end = pr["points"][-1][0]
        wb_end = prov[-1][0][:4] if prov else "n/a"
        res_note = (f"<p><strong>Proved reserves do not extend with the key.</strong> The API "
                    f"reports the same {api_end} endpoint as the public workbook ({wb_end}), "
                    f"with dataset coverage {pr.get('period', ['?','?'])[0]}–"
                    f"{pr.get('period', ['?','?'])[1]}. The gap is the dataset, not the "
                    f"access route — I expected the key to close it and it does not.</p>")

    brk_flag = ""
    if breaks:
        rows = "".join(f"<tr><td>{s}</td><td class='n'>{m}</td><td class='n'>{d:+.2f}</td>"
                       f"<td class='n'>{n}</td></tr>" for s, m, d, n in breaks)
        brk_flag = f"""<div class="flag">
  <h4>All three OPEC series break in the same month</h4>
  <p>Each series takes its largest move in three years at the same date. A simultaneous
  step across crude production, total supply and spare capacity is a change in what the
  "OPEC" aggregate counts — members entering or leaving the grouping — not a market event.
  Do not compute growth across it, and do not read Saudi spare capacity falling to exactly
  0.00 as a physical collapse; it is unpublished on the new basis.</p>
  <div class="tbl-wrap"><table><caption>Detected structural breaks</caption>
  <thead><tr><th>Series</th><th class="n">Break month</th><th class="n">Step (mb/d)</th>
  <th class="n">Months after</th></tr></thead><tbody>{rows}</tbody></table></div>
</div>"""

    return f"""<section>
  <h2><span class="num">Topic 06</span>OPEC production, and what the API key did not fix</h2>
  <p class="lede">Now served by the EIA v2 API. The four storage series it returns match the
  public workbooks to the barrel — Cushing 20,955, SPR 304,809, commercial 406,987 — so the
  two routes independently corroborate each other. OPEC production is new; it also needs the
  most careful handling on this page.</p>
  {res_note}{''.join(charts)}{brk_flag}
  {('<div class="flag warn"><h4>Unresolved</h4><p>' + html.escape('; '.join(notes)) + '</p></div>') if notes else ''}
</section>"""

# ---------- render ----------
CSS = """
:root{
 --bg:#FBF8F3; --panel:#FFFFFF; --ink:#231D14; --ink-2:#5C5245; --ink-3:#8A7F70;
 --line:#E3DACB; --accent:#B0741F; --accent-fade:rgba(176,116,31,.13);
 --teal:#1E6B6B; --good:#4F7D4A; --warn:#C8862A; --crit:#B4442E;
 --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
 --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
 --sans:system-ui,-apple-system,"Segoe UI",sans-serif;
}
@media (prefers-color-scheme:dark){
 :root{--bg:#15130F; --panel:#1E1B16; --ink:#F2EBDF; --ink-2:#B8AD9B; --ink-3:#8A7F70;
  --line:#332D24; --accent:#D9A24E; --accent-fade:rgba(217,162,78,.15);
  --teal:#4FA3A3; --good:#7FAE6F; --warn:#D9A24E; --crit:#D9705C;}
}
:root[data-theme="dark"]{--bg:#15130F; --panel:#1E1B16; --ink:#F2EBDF; --ink-2:#B8AD9B;
 --ink-3:#8A7F70; --line:#332D24; --accent:#D9A24E; --accent-fade:rgba(217,162,78,.15);
 --teal:#4FA3A3; --good:#7FAE6F; --warn:#D9A24E; --crit:#D9705C;}
:root[data-theme="light"]{--bg:#FBF8F3; --panel:#FFFFFF; --ink:#231D14; --ink-2:#5C5245;
 --ink-3:#8A7F70; --line:#E3DACB; --accent:#B0741F; --accent-fade:rgba(176,116,31,.13);
 --teal:#1E6B6B; --good:#4F7D4A; --warn:#C8862A; --crit:#B4442E;}

*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
 line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding:38px 22px 80px}
header.top{border-bottom:2px solid var(--accent);padding-bottom:20px;margin-bottom:34px}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;
 color:var(--accent);margin-bottom:10px}
h1{font-family:var(--serif);font-size:clamp(27px,4vw,40px);line-height:1.12;margin:0 0 10px;
 text-wrap:balance;font-weight:600}
.sub{color:var(--ink-2);max-width:62ch;font-size:15px}
section{margin:44px 0 0}
h2{font-family:var(--serif);font-size:25px;margin:0 0 6px;font-weight:600;text-wrap:balance}
h2 .num{font-family:var(--mono);font-size:12px;color:var(--accent);
 display:block;letter-spacing:.12em;margin-bottom:5px;font-weight:400}
h3{font-family:var(--serif);font-size:19px;margin:26px 0 10px;font-weight:600}
h4{font-size:13.5px;margin:0 0 9px;font-weight:600}
.lede{color:var(--ink-2);max-width:66ch;margin:0 0 18px}
p{max-width:66ch}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:5px;
 padding:20px 22px;margin:18px 0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(212px,1fr));gap:13px;margin:20px 0}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:5px;padding:14px 15px}
.tile-h{font-size:11.5px;color:var(--ink-2);display:flex;justify-content:space-between;
 align-items:center;gap:8px;margin-bottom:7px;font-weight:500}
.tile-v{font-family:var(--mono);font-size:26px;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.tile-v .u{font-size:11px;color:var(--ink-3);margin-left:5px;letter-spacing:0}
.tile-n{font-size:11px;color:var(--ink-3);margin-top:6px;font-family:var(--mono)}
.pill{font-family:var(--mono);font-size:9.5px;padding:2px 6px;border-radius:2px;
 letter-spacing:.04em;white-space:nowrap}
.pill.good{background:rgba(79,125,74,.16);color:var(--good)}
.pill.warn{background:rgba(200,134,42,.18);color:var(--warn)}
.pill.crit{background:rgba(180,68,46,.16);color:var(--crit)}
.chart{width:100%;height:auto;display:block;margin:8px 0 4px;overflow:visible}
.grid{stroke:var(--line);stroke-width:1}
.axis{stroke:var(--ink-3);stroke-width:1}
.ytick,.xtick{font-family:var(--mono);font-size:9.5px;fill:var(--ink-3)}
.ytick{text-anchor:end}.xtick{text-anchor:middle}
.lgd{font-family:var(--mono);font-size:10px}
.blab{font-family:var(--sans);font-size:11px;fill:var(--ink-2);text-anchor:end}
.bval{font-family:var(--mono);font-size:10.5px;fill:var(--ink-2);font-variant-numeric:tabular-nums}
.cap{font-family:var(--mono);font-size:10.5px;color:var(--ink-3);margin-top:4px}
.tbl-wrap{overflow-x:auto;margin:16px 0}
table{border-collapse:collapse;width:100%;font-size:13px;min-width:400px}
caption{text-align:left;font-size:11.5px;color:var(--ink-2);padding-bottom:8px;font-weight:500}
th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left}
th{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.07em;
 color:var(--ink-3);font-weight:500}
td.n,th.n{text-align:right;font-family:var(--mono);font-variant-numeric:tabular-nums}
.pairgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:13px}
.pairbox{background:var(--panel);border:1px solid var(--line);border-radius:5px;padding:13px 15px}
.pairbox .hs{font-family:var(--mono);font-size:9.5px;color:var(--ink-3);font-weight:400}
.pcols{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.plab{font-family:var(--mono);font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;
 padding-bottom:5px;margin-bottom:5px;border-bottom:1px solid var(--line)}
.plab.out{color:var(--good)}.plab.in{color:var(--crit)}
.pr{display:flex;justify-content:space-between;gap:8px;font-size:11.5px;padding:2px 0}
.pn{color:var(--ink-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pv{font-family:var(--mono);font-variant-numeric:tabular-nums;color:var(--ink)}
.none{font-size:11px;color:var(--ink-3);font-style:italic}
.repblock{margin:26px 0}
.repblock h3 .yr{font-family:var(--mono);font-size:11px;color:var(--ink-3);font-weight:400}
.flag{border-left:3px solid var(--crit);background:var(--panel);padding:13px 16px;margin:14px 0;
 border-radius:0 4px 4px 0}
.flag.warn{border-left-color:var(--warn)}
.flag.ok{border-left-color:var(--good)}
.flag h4{margin:0 0 5px;font-family:var(--mono);font-size:10.5px;letter-spacing:.06em;
 text-transform:uppercase;color:var(--ink-2)}
.flag p{margin:0;font-size:13px;color:var(--ink-2);max-width:70ch}
.ctx{font-size:11.5px;color:var(--ink-3);font-style:italic}
ul{max-width:68ch;padding-left:20px}li{margin:5px 0;color:var(--ink-2);font-size:14px}
code{font-family:var(--mono);font-size:.9em;background:var(--accent-fade);padding:1px 4px;border-radius:2px}
footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--line);
 font-family:var(--mono);font-size:10.5px;color:var(--ink-3)}
@media (max-width:620px){.pcols{grid-template-columns:1fr}}
"""

def money(v): return f"{v/1e9:,.1f}"

html_out = f"""<title>Petroleum trade pairings &amp; US crude storage</title>
<style>{CSS}</style>
<div class="wrap">
<header class="top">
  <div class="eyebrow">Comtrade · EIA · DGCI&amp;S TRADESTAT</div>
  <h1>Petroleum trade pairings and the US crude storage picture</h1>
  <p class="sub">Where the USA, Mexico and the GCC buy and sell crude, refined products,
  LPG and lubricants — and why US storage levels at Cushing sit underneath the whole
  crude-slate question.</p>
</header>

<section>
  <h2><span class="num">Topic 01 — new</span>US crude storage and reserves</h2>
  <p class="lede">Every series below is EIA weekly or annual data, read straight from the
  agency's own workbooks. The headline: the two buffers that matter most to the physical
  crude market — Cushing and the SPR — are both far below their historical peaks.</p>
  <div class="tiles">{''.join(tiles)}</div>

  <div class="panel">
    <h3>Cushing, Oklahoma — the WTI delivery hub</h3>
    {area_chart(cush, accent="var(--crit)", fill="rgba(180,68,46,.12)", unit="thousand bbl")}
    <div class="cap">Weekly stocks, thousand barrels · {cush[0][0] if cush else ''} to {cush[-1][0] if cush else ''}
    · latest {mb(S['W_EPC0_SAX_YCUOK_MBBL']['last'][1])}M bbl vs
    {mb(S['W_EPC0_SAX_YCUOK_MBBL']['max'][1])}M peak ({S['W_EPC0_SAX_YCUOK_MBBL']['max'][0][:7]})</div>
  </div>

  <div class="panel">
    <h3>Commercial crude versus the Strategic Petroleum Reserve</h3>
    {multi_line([("Commercial","var(--teal)",comm),("SPR","var(--accent)",spr)])}
    <div class="cap">Weekly stocks, thousand barrels. The SPR line is the federal buffer;
    commercial is industry working stock.</div>
  </div>

  <div class="panel">
    <h3>US crude oil proved reserves</h3>
    {area_chart(prov, accent="var(--teal)", fill="rgba(30,107,107,.13)", y_zero=True, unit="million bbl")}
    <div class="cap">Annual, million barrels · series runs {prov[0][0][:4] if prov else ''}–{prov[-1][0][:4] if prov else ''}.
    Note this EIA workbook stops at {prov[-1][0][:4] if prov else 'n/a'} — proved reserves are
    published with a long lag and are <em>not</em> a storage measure.</div>
  </div>

  <div class="flag warn">
    <h4>Two different things called "reserves"</h4>
    <p>Proved reserves (41,151 million bbl, above) are oil still in the ground — a geological
    and economic estimate revised annually. The SPR and Cushing are barrels already produced
    and sitting in tanks and caverns. They move on entirely different clocks, and only the
    second kind can be delivered against a futures contract next month.</p>
  </div>
</section>

<section>
  <h2><span class="num">Topic 02</span>Why Cushing and US reserves drive the crude mix</h2>
  <p class="lede">The US is the world's largest oil producer and still buys more crude than it
  sells. That is not a contradiction — it is a grade mismatch, and the trade data shows it.</p>

  <div class="tiles">
    <div class="tile"><div class="tile-h">US crude exports<span class="pill good">sells</span></div>
      <div class="tile-v">{money(crude_x)}<span class="u">$bn</span></div>
      <div class="tile-n">HS 2709 · {prod.get('USA',{}).get('year','')}</div></div>
    <div class="tile"><div class="tile-h">US crude imports<span class="pill crit">buys</span></div>
      <div class="tile-v">{money(crude_m)}<span class="u">$bn</span></div>
      <div class="tile-n">HS 2709 · {prod.get('USA',{}).get('year','')}</div></div>
    <div class="tile"><div class="tile-h">Net crude position<span class="pill crit">deficit</span></div>
      <div class="tile-v">{money(crude_x-crude_m)}<span class="u">$bn</span></div>
      <div class="tile-n">still a net crude importer</div></div>
  </div>

  <p>US shale produces light sweet crude. Much of the Gulf Coast refining base was built
  to run heavy sour barrels, which yield more diesel and feed cokers that light crude cannot
  fill. So the country exports its own light barrels and imports heavier ones — a two-way
  trade in the same HS line, driven by grade rather than by shortage.
  <span class="ctx">Refinery configuration and SPR grade composition are established industry
  context, not conclusions from this dataset.</span></p>

  {uv_table('M','US crude imports — implied unit value by partner (grade proxy)')}
  {uv_table('X','US crude exports — implied unit value by partner (grade proxy)')}

  <div class="flag ok">
    <h4>Why Cushing specifically</h4>
    <p>Cushing is the physical delivery point for the WTI contract. When its tanks run
    toward operating minimum, the barrels available to settle that contract thin out, and WTI
    trades more on local tank economics than on global supply. At
    {mb(S['W_EPC0_SAX_YCUOK_MBBL']['last'][1])}M bbl — {S['W_EPC0_SAX_YCUOK_MBBL']['pct_of_max']:.0f}%
    of its 2017 peak — the hub is a small buffer under a very large benchmark.</p>
  </div>
</section>

<section>
  <h2><span class="num">Topic 03</span>Who is long and who is short</h2>
  <p class="lede">Net petroleum position across the thirteen HS lines that make up crude,
  refined products, LPG, waxes, coke and lubricants. Positive means the country sells more
  than it buys.</p>
  {bar_chart(prof_rows)}
  <div class="cap">US$ bn, net (exports − imports), latest complete reported year per country.
  Basis differs by country because reporting granularity does — see the table below.</div>

  <div class="tbl-wrap"><table><caption>Which figure each country's bar is built from</caption>
  <thead><tr><th>Country</th><th>Year</th><th>Basis used</th><th class="n">X / M ($bn)</th></tr></thead>
  <tbody>{''.join(f"<tr><td>{html.escape(n)}</td><td>{y}</td><td>{html.escape(s)}</td>"
                  f"<td class='n'>{xm}</td></tr>" for n, y, s, xm in basis_rows)}</tbody></table></div>

  <h3>United States, by product</h3>
  {bar_chart(us_prod_rows)}
  <div class="cap">US$ bn net by HS line. The US is short crude and long almost every
  refined product and gas liquid — the refining-margin business in one chart.</div>
</section>

<section>
  <h2><span class="num">Topic 04</span>Key import–export pairings</h2>
  <p class="lede">For each reporter and product, the largest counterparties on both sides.
  Values are US$ bn for the year shown.</p>
  {''.join(pair_sections) if pair_sections else '<p class="none">pairings data not yet collected</p>'}

  <div class="flag">
    <h4>Most GCC exporters do not name their customers</h4>
    <p>Before reading any pairing above: several reporters book the bulk of their exports to
    residual "not elsewhere specified" buckets rather than to a country. UAE records
    $162.8bn of crude to <em>Areas, nes</em>; Saudi Arabia records $134.7bn to
    <em>Other Asia, nes</em>. These are not counterparties, and treating them as such would
    invent the largest trade flows in the dataset. They are excluded from every panel above,
    which is why the GCC panels look thin — the trade is real, the destination is withheld.</p>
  </div>

  <div class="tbl-wrap"><table><caption>Export destination disclosure, focus products</caption>
  <thead><tr><th>Reporter</th><th>Year</th><th class="n">Named destinations</th>
  <th class="n">Undisclosed ($bn)</th><th class="n">Total ($bn)</th></tr></thead>
  <tbody>{''.join(
      f"<tr><td>{html.escape(r)}</td><td>{y}</td>"
      f"<td class='n'>{p:.0f}%</td><td class='n'>{h:,.1f}</td>"
      f"<td class='n'>{t:,.1f}</td></tr>" for r, y, p, h, t in DISC_ROWS)}</tbody></table></div>
  <div class="cap">Share of export value booked to a named country across HS 2709, 271012,
  271019, 271112, 271113 and 3403. Low percentages mean the reporter's own data cannot
  support bilateral analysis.</div>

  <h3>Reading the GCC from the buyer's side instead</h3>
  <p>Where a seller withholds destinations, the importer's own declaration recovers the
  pairing. Below: suppliers named by the United States, India and Mexico in their own
  import filings — the same trade, seen from the end that discloses it.</p>
  {''.join(f'''<div class="tbl-wrap"><table><caption>{PRODNAME.get(code,code)} — suppliers named by importers (US$ bn)</caption>
  <thead><tr><th>Supplier</th>{''.join(f'<th class="n">{i}</th>' for i in MIRROR_SRC)}<th class="n">Total</th></tr></thead>
  <tbody>{''.join(f"<tr><td>{html.escape(str(src))}</td>" + ''.join(f"<td class='n'>{(byimp.get(i,0)/1e9):,.2f}</td>" for i in MIRROR_SRC) + f"<td class='n'>{tot/1e9:,.2f}</td></tr>" for src, byimp, tot in mirror_suppliers(code))}</tbody></table></div>'''
   for code in ["2709", "271019", "271112"])}

  <h3>The largest pairing in the region, and why you must read it from the US side</h3>
  <p>US refined-product exports into Mexico are the biggest petroleum pairing here. But the
  two countries do not agree on its size: Mexico's declared gasoline imports are a fraction
  of what the US declares shipping. The other product lines reconcile, so this is a
  line-specific reporting gap, not a broken record.</p>
  <div class="tbl-wrap"><table><caption>United States → Mexico: each side's own declaration</caption>
  <thead><tr><th>Product</th><th>HS</th><th class="n">US declares (exports)</th>
  <th class="n">Mexico declares (imports)</th><th class="n">Mex / US</th></tr></thead>
  <tbody>{''.join(
      f"<tr><td>{html.escape(l)}</td><td class='n'>{c}</td>"
      f"<td class='n'>{u/1e9:,.2f}</td><td class='n'>{m/1e9:,.2f}</td>"
      f"<td class='n'>{(f'{r:.2f}×' if r is not None else '—')}</td></tr>"
      for l, c, u, m, r in MIRROR)}</tbody></table></div>
  <div class="cap">US$ bn. Gasoline is the outlier — treat Mexico's own gasoline import line
  as unusable and take the US export figure instead.</div>
</section>

<section>
  <h2><span class="num">Topic 05</span>What this data can and cannot tell you</h2>
  <p class="lede">Findings from building the pipeline. Each one changes how the numbers above
  should be read.</p>

  <div class="flag">
    <h4>The two granularity levels fail in different countries</h4>
    <p>Neither the chapter aggregate nor the HS-6 detail is reliable everywhere, and they
    break in opposite directions. India's chapter-27 imports are <em>correct</em>
    ($209.1bn, against DGCI&amp;S's $203.4bn — a 3% reconciliation) while its HS-6 import
    detail is almost entirely absent: crude at the six-digit level reads $0.28bn instead of
    roughly $140bn. Mexico and Oman are the mirror image — their HS-6 detail is sound but
    their chapter aggregates read $0.7bn and $2.5bn against HS-6 sums of $19.7bn and
    $44.8bn. Pick one level for a cross-country table and some countries will be wrong by
    an order of magnitude.</p>
  </div>

  <div class="flag">
    <h4>Qatar's LNG is missing at HS-6; Bahrain reports nothing</h4>
    <p>Qatar's chapter-27 exports total $79.6bn, but its HS-6 detail accounts for only
    $15.0bn — all of it crude, with no LNG (HS 271111) recorded at all. Roughly $64bn of
    the region's most important gas trade is invisible at product level. Bahrain reports
    essentially no chapter-27 trade in either direction. Both need partner-declared
    (mirror) data for any product-level view, which is why they carry no pairing panel.</p>
  </div>

  <div class="flag">
    <h4>Partner names are not in the API response</h4>
    <p>The preview endpoint returns <code>partnerDesc: null</code> on every row — only the
    numeric partner code is populated. Matching on the name field silently yields zero for
    every counterparty; the largest pairing in this dataset first appeared as
    "US → Mexico, $0.00bn". Names here are resolved from Comtrade's own
    <code>partnerAreas</code> reference file, and region aggregates are excluded so
    counterparties are not double-counted.</p>
  </div>

  <div class="flag">
    <h4>Diesel and base oil cannot be separated at HS-6</h4>
    <p>HS 271019 bundles gasoil/diesel, kerosene, fuel oil <em>and</em> lubricating base oils
    into one line. No six-digit query can split lube-oil exports from diesel exports —
    that needs national tariff detail (India's 8-digit TRADESTAT, US HTS 10-digit).
    The $35.7bn "India 271019 exports" figure is mostly diesel, not lubricants.</p>
  </div>

  <div class="flag warn">
    <h4>UAE stops reporting after 2023; Qatar after 2024</h4>
    <p>Verified with retries, not inferred from a single failed call. UAE 2024 and 2025 are
    genuinely absent, so UAE figures here are 2023 and are not comparable year-on-year with
    Saudi or US 2025 numbers. Kuwait's 2025 query hit the API row cap and was excluded.</p>
  </div>

  <div class="flag warn">
    <h4>Queries that hit the row ceiling are incomplete, not empty</h4>
    <p>The public preview returns at most 500 rows per query. Any query that comes back at
    exactly the ceiling has had counterparties silently truncated — the response looks
    perfectly valid. {('Affected here: ' + ', '.join(f'{r} {n}' for r, c, n in CAPPED) + '.') if CAPPED else 'No query hit the ceiling in this run.'}
    Those partner lists are a floor, not a complete set.</p>
  </div>

  <div class="flag warn">
    <h4>The API silently drops data when throttled</h4>
    <p>A first pass without retries showed 2023 missing for six of nine countries. With
    backoff and retry, every one of those years returned complete data — 4 throttled calls
    versus 5 genuinely empty ones. An unretried collector would have reported those years
    as zero trade.</p>
  </div>

  <div class="flag warn">
    <h4>How the reporting year was chosen — and where that rule is weak</h4>
    <p>For each country the latest year was accepted only if its chapter-27 exports and
    imports both exceeded 55% of that country's own five-year peak, which correctly rejects
    trailing partial years (UAE 2024–25, Qatar 2025). The rule is only valid for trailing
    years: it also flagged Qatar 2021–23, but that is the 2022 gas-price spike moving the
    ratio, not missing data. And because it reads the chapter aggregate, it is itself
    unreliable for Mexico and Oman, whose aggregates are broken.</p>
  </div>

  <div class="flag warn">
    <h4>Paywalled and unavailable sources</h4>
    <p>OilPriceAPI on this account returns HTTP 403 for OPEC production, storage and
    inventories, and requires a paid plan for any price history — it serves current spot only.
    An EIA API key now supplies OPEC production and the full storage series directly
    {('(Topic 06)' if eia_api else '(not yet configured)')}, so that gap is closed from a
    different source rather than from OilPriceAPI. Still missing: no S&amp;P Global commodity
    feed is connected to this session — the finance connector available is MSCI Private Assets
    (private capital, real assets and index data), which carries no petroleum series, so
    Platts-style assessments remain out of reach. And EIA proved reserves end at 2021 by
    <em>both</em> routes.</p>
  </div>
</section>

{opec_block()}

<footer>
  Sources — UN Comtrade public preview (HS, annual, reporter-declared); US EIA weekly
  petroleum status and annual proved reserves workbooks; DGCI&amp;S TRADESTAT EIDB via
  india-trade-data-analysis. Values are nominal US$, not volume-adjusted; Comtrade figures
  are reporter-declared and differ from mirror (partner-declared) data.
  Built {os.popen('date "+%d %B %Y"').read().strip()}.
</footer>
</div>
"""

out = "/Users/umashankar/Downloads/code/petroleum_trade_pairings_dashboard.html"
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w") as f: f.write(html_out)
print("wrote", out, len(html_out), "bytes")
print("profile rows:", len(prof_rows), "| pair sections:", len(pair_sections),
      "| uv rows:", len(uv_rows))
