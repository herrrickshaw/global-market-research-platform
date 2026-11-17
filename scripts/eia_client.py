"""EIA API v2 client.

Unlocks what the keyless dnav workbooks cannot serve: OPEC production, the full
storage/inventory series, and international data.

Key resolution order:
  1. $EIA_API_KEY
  2. EIA_API_KEY= line in ~/.config/market-secrets/credentials.env  (gitignored)

The key is sent as an X-Api-Key header, never in the query string, so it does not
land in logs, shell history, or the on-disk response cache. If a deployment rejects
the header the client retries once with the api_key parameter, and in that case the
cache key is still computed from the key-free params.

Falls back to nothing: callers should treat KeyMissing as "use eia.py workbooks".
"""
import json, os, time, hashlib, urllib.request, urllib.parse, urllib.error

BASE = "https://api.eia.gov/v2"
CRED = os.path.expanduser("~/.config/market-secrets/credentials.env")
CACHE = os.path.expanduser(os.environ.get("EIA_CACHE_DIR", "~/.cache/eia"))
UA = "market-research-platform/1.0 (EIA v2 client)"


class KeyMissing(RuntimeError):
    pass


def _read_key():
    k = os.environ.get("EIA_API_KEY", "").strip()
    if k:
        return k
    if os.path.exists(CRED):
        with open(CRED) as f:
            for line in f:
                line = line.strip()
                if line.startswith("EIA_API_KEY=") and not line.startswith("#"):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v
    raise KeyMissing(
        "No EIA_API_KEY found.\n"
        f"  Add it to {CRED} as:  EIA_API_KEY=<your key>\n"
        "  Get a free key at https://www.eia.gov/opendata/register.php"
    )


def have_key():
    try:
        _read_key()
        return True
    except KeyMissing:
        return False


def _ensure_cache():
    """$HOME is itself a public git repo here, so the cache self-ignores rather than
    relying on a root .gitignore rule (today it survives only via a blanket *.json)."""
    os.makedirs(CACHE, exist_ok=True)
    gi = os.path.join(CACHE, ".gitignore")
    if not os.path.exists(gi):
        with open(gi, "w") as f:
            f.write("# EIA response cache - never commit\n*\n")


def _cache_path(route, params):
    blob = json.dumps({"route": route, "params": params}, sort_keys=True)
    return os.path.join(CACHE, hashlib.md5(blob.encode()).hexdigest()[:20] + ".json")


def request(route, params=None, use_cache=True, tries=4, pause=1.5):
    """GET {BASE}/{route}. params values may be lists (repeated as x[]=a&x[]=b)."""
    key = _read_key()
    params = dict(params or {})
    _ensure_cache()
    cp = _cache_path(route, params)
    if use_cache and os.path.exists(cp):
        with open(cp) as f:
            return json.load(f)

    pairs = []
    for k, v in params.items():
        if isinstance(v, (list, tuple)):
            pairs.extend((k, str(x)) for x in v)
        else:
            pairs.append((k, str(v)))
    qs = urllib.parse.urlencode(pairs)
    url = f"{BASE}/{route.strip('/')}?{qs}" if qs else f"{BASE}/{route.strip('/')}"

    last = None
    for attempt in range(tries):
        for mode in ("header", "param"):
            u = url
            headers = {"User-Agent": UA, "Accept": "application/json"}
            if mode == "header":
                headers["X-Api-Key"] = key
            else:
                u = u + ("&" if "?" in u else "?") + "api_key=" + urllib.parse.quote(key)
            try:
                req = urllib.request.Request(u, headers=headers)
                with urllib.request.urlopen(req, timeout=60) as r:
                    d = json.loads(r.read())
                if use_cache:
                    with open(cp, "w") as f:
                        json.dump(d, f)
                return d
            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read().decode()[:300]
                except Exception:
                    pass
                last = f"HTTP {e.code} {body}"
                # 403 on header mode -> try param mode; otherwise stop trying modes
                if e.code in (401, 403) and mode == "header":
                    continue
                if e.code in (429, 500, 502, 503):
                    break          # back off, then retry both modes
                raise RuntimeError(f"EIA {route}: {last}") from None
            except Exception as e:
                last = str(e)
                break
        time.sleep(pause * (2 ** attempt))
    raise RuntimeError(f"EIA {route} failed after {tries} attempts: {last}")


def discover(route=""):
    """Walk the self-describing route tree. Returns child routes, frequencies,
    facet names and data columns for `route` - so callers never hardcode a guess."""
    d = request(route, use_cache=True).get("response", {})
    return {
        "id": d.get("id"), "name": d.get("name"),
        "routes": [(r.get("id"), r.get("name")) for r in (d.get("routes") or [])],
        "frequencies": [f.get("id") for f in (d.get("frequency") or [])],
        "facets": [f.get("id") for f in (d.get("facets") or [])],
        "data_cols": list((d.get("data") or {}).keys()),
        "period": (d.get("startPeriod"), d.get("endPeriod")),
    }


def facet_values(route, facet):
    d = request(f"{route}/facet/{facet}", use_cache=True).get("response", {})
    return [(f.get("id"), f.get("name")) for f in (d.get("facets") or [])]


def series(route, data=("value",), facets=None, frequency=None,
           start=None, end=None, sort_desc=True, length=5000, offset=0):
    """Fetch /{route}/data. Returns list of row dicts."""
    p = {"data[]": list(data), "length": length, "offset": offset}
    if frequency:
        p["frequency"] = frequency
    if start:
        p["start"] = start
    if end:
        p["end"] = end
    if sort_desc:
        p["sort[0][column]"] = "period"
        p["sort[0][direction]"] = "desc"
    for k, vals in (facets or {}).items():
        p[f"facets[{k}][]"] = list(vals) if isinstance(vals, (list, tuple)) else [vals]
    return request(f"{route.strip('/')}/data", p).get("response", {}).get("data", [])


def to_points(rows, period="period", value="value"):
    """[(period, float)] ascending, dropping nulls."""
    out = []
    for r in rows:
        v = r.get(value)
        if v is None:
            continue
        try:
            out.append((str(r[period]), float(v)))
        except (TypeError, ValueError):
            continue
    return sorted(out)
