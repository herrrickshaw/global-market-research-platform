#!/usr/bin/env python3
"""Collect the three datasets the EIA key unlocks, into one JSON the dashboard reads.

    python3 ~/scripts/eia_opec.py

Writes ~/scripts/data/eia_api_series.json:
    opec_production   per-country / aggregate crude production
    storage           Cushing, SPR, commercial crude weekly stocks
    proved_reserves   annual, past where the public workbook stops (2021)

Without a key this exits 1 and changes nothing, leaving the keyless workbook route
(eia.py) as the dashboard's source. Routes and facet ids are resolved at runtime via
eia_client.discover(), so a dataset being reorganised surfaces as a clear message
rather than a wrong number.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eia_client as E

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "eia_api_series.json")


def pick_facet(route, facet, *keywords):
    """Return facet ids whose name matches any keyword (case-insensitive)."""
    try:
        vals = E.facet_values(route, facet)
    except Exception:
        return []
    kws = [k.lower() for k in keywords]
    return [(i, n) for i, n in vals if any(k in str(n).lower() for k in kws)]


# Series ids confirmed present in both the dnav workbooks and the API's series facet.
STORAGE_SERIES = {
    "cushing":    "W_EPC0_SAX_YCUOK_MBBL",   # Cushing OK ending stocks excl SPR
    "spr":        "WCSSTUS1",                # US ending stocks of crude in SPR
    "commercial": "WCESTUS1",                # US ending stocks excl SPR
    "total":      "WCRSTUS1",                # US ending stocks of crude incl SPR
}


def collect_storage():
    """Cushing / SPR / commercial / total crude, weekly, by explicit series id."""
    route = "petroleum/stoc/wstk"
    d = E.discover(route)
    freq = "weekly" if "weekly" in (d["frequencies"] or []) else (d["frequencies"] or [None])[0]
    out = {}
    for label, sid in STORAGE_SERIES.items():
        try:
            rows = E.series(route, data=("value",), facets={"series": [sid]},
                            frequency=freq, length=5000)
            if not rows:
                out[label] = {"series_id": sid, "error": "no rows returned"}
                continue
            out[label] = {"series_id": sid,
                          "name": rows[0].get("series-description"),
                          "unit": rows[0].get("units"),
                          "points": E.to_points(rows)}
        except Exception as e:
            out[label] = {"series_id": sid, "error": str(e)}
    return out


def collect_reserves():
    route = "petroleum/crd/pres"
    d = E.discover(route)
    freq = (d["frequencies"] or ["annual"])[0]
    rows = E.series(route, data=("value",), frequency=freq, length=5000)
    return {"route": route, "period": d["period"], "rows": len(rows),
            "points": E.to_points(rows)}


# Discovered via eia_verify: STEO seriesId facet carries the OPEC aggregates.
# COPR_OPEC is crude production specifically - NOT total petroleum supply (PAPR_OPEC),
# which includes NGLs and would overstate crude by several mb/d.
STEO_SERIES = [
    ("COPR_OPEC", "OPEC crude oil production"),
    ("PAPR_OPEC", "Total OPEC petroleum supply (incl. NGLs)"),
    ("COPS_SA",   "Saudi Arabia spare crude capacity"),
]


def collect_opec():
    """OPEC crude production from STEO, by explicit series id."""
    out = {"route": "steo", "series": {}}
    d = E.discover("steo")
    freq = "monthly" if "monthly" in (d["frequencies"] or []) else \
           (d["frequencies"] or [None])[0]
    for sid, label in STEO_SERIES:
        try:
            rows = E.series("steo", data=("value",), facets={"seriesId": [sid]},
                            frequency=freq, length=3000)
            if not rows:
                out["series"][sid] = {"label": label, "error": "no rows"}
                continue
            out["series"][sid] = {
                "label": label,
                "name": rows[0].get("seriesDescription") or rows[0].get("series-description"),
                "unit": rows[0].get("unit") or rows[0].get("units"),
                "points": E.to_points(rows),
            }
        except Exception as e:
            out["series"][sid] = {"label": label, "error": str(e)}
    return out


def main():
    if not E.have_key():
        try:
            E._read_key()
        except E.KeyMissing as e:
            print(e)
        print("\nNothing written. Dashboard continues on the keyless workbook route.")
        return 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    payload = {}
    for name, fn in [("storage", collect_storage),
                     ("proved_reserves", collect_reserves),
                     ("opec_production", collect_opec)]:
        print(f"-- {name} ...", flush=True)
        try:
            payload[name] = fn()
            print(f"   ok")
        except Exception as e:
            payload[name] = {"error": str(e)}
            print(f"   FAILED: {e}")

    with open(OUT, "w") as f:
        json.dump(payload, f, indent=1)
    print(f"\nwrote {OUT}")

    st = payload.get("storage", {})
    for k, v in st.items():
        if isinstance(v, dict) and v.get("points"):
            last = v["points"][-1]
            print(f"   {k:11s} {last[0]}  {last[1]:,.0f}  ({v.get('name','')[:48]})")
        elif isinstance(v, dict):
            print(f"   {k:11s} {v.get('error')}")
    pr = payload.get("proved_reserves", {})
    if pr.get("points"):
        print(f"   reserves   latest {pr['points'][-1][0]} = {pr['points'][-1][1]:,.0f} "
              f"(workbook route stopped at 2021)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
