#!/usr/bin/env python3
"""Verify the EIA API key and discover the routes we need.

Run after adding EIA_API_KEY to ~/.config/market-secrets/credentials.env:

    python3 ~/scripts/eia_verify.py

Prints, for each target, whether it is reachable and a real sample value. Route
paths are DISCOVERED from the API's own tree, not assumed - if EIA reorganises a
dataset this script reports the actual children instead of failing silently.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eia_client as E

OK, WARN, BAD = "  \033[32m OK \033[0m", "  \033[33mWARN\033[0m", "  \033[31mFAIL\033[0m"


def head(t):
    print(f"\n{'='*70}\n{t}\n{'='*70}")


def main():
    if not E.have_key():
        head("EIA API key not configured")
        try:
            E._read_key()
        except E.KeyMissing as e:
            print(e)
        print("\nThe keyless dnav workbook route still works meanwhile "
              "(scripts/../eia.py), which is what the current dashboard uses.")
        return 1

    head("1. Key check")
    try:
        top = E.discover("")
        print(f"{OK} key accepted · {len(top['routes'])} top-level datasets")
        for rid, nm in top["routes"]:
            print(f"       {rid:22s} {nm}")
    except Exception as e:
        print(f"{BAD} key rejected: {e}")
        return 1

    # ---- 2. weekly petroleum stocks (Cushing, SPR, commercial) ----
    head("2. Storage & inventories")
    for route in ["petroleum/stoc/wstk", "petroleum/stoc/typ"]:
        try:
            d = E.discover(route)
            print(f"{OK} {route} · facets={d['facets']} freq={d['frequencies']} "
                  f"period={d['period'][0]}..{d['period'][1]}")
        except Exception as e:
            print(f"{WARN} {route}: {e}")

    try:
        rows = E.series("petroleum/stoc/wstk", data=("value",),
                        frequency="weekly", length=3)
        print(f"{OK} sample rows: {rows[:2]}")
    except Exception as e:
        print(f"{WARN} weekly stocks sample failed: {e}")

    # ---- 3. proved reserves (fills the gap where the workbook stops at 2021) ----
    head("3. Proved reserves")
    for route in ["petroleum/crd/pres"]:
        try:
            d = E.discover(route)
            print(f"{OK} {route} · facets={d['facets']} period={d['period'][0]}..{d['period'][1]}")
            rows = E.series(route, frequency=(d["frequencies"] or ["annual"])[0], length=3)
            print(f"       latest: {rows[:2]}")
        except Exception as e:
            print(f"{WARN} {route}: {e}")

    # ---- 4. OPEC production ----
    head("4. OPEC production")
    found = False
    # STEO carries OPEC aggregates; international carries per-country production.
    for route in ["steo", "international"]:
        try:
            d = E.discover(route)
            print(f"{OK} {route} reachable · facets={d['facets']} freq={d['frequencies']}")
            for f in d["facets"]:
                try:
                    vals = E.facet_values(route, f)
                except Exception:
                    continue
                hits = [(i, n) for i, n in vals
                        if any(k in str(n).lower() for k in ("opec", "saudi", "crude production"))]
                if hits:
                    found = True
                    print(f"       facet '{f}' matches: {hits[:6]}")
        except Exception as e:
            print(f"{WARN} {route}: {e}")
    print(("  OPEC-related facets located — see matches above."
           if found else
           "  No OPEC facet matched automatically; inspect facet lists manually."))

    head("Summary")
    print("  Storage/inventories, proved reserves and OPEC production are the three "
          "things the key adds over the keyless workbooks.\n"
          "  Wire results into the dashboard with:  python3 ~/scripts/eia_opec.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
