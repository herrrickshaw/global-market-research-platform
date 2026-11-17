"""Comtrade public-preview client with disk cache, retry, and explicit
'throttled vs genuinely empty' accounting. The preview endpoint caps at
500 rows, so every caller must keep a single query under that."""
import json,os,time,hashlib,urllib.request,urllib.error

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
BASE="https://comtradeapi.un.org/public/v1/preview/C/A/HS"
CACHE=os.path.join(os.path.dirname(os.path.abspath(__file__)),"cache")
ROW_CAP=500
STATS={"cache_hit":0,"fetched":0,"empty":0,"throttled":0,"error":0,"capped":0}

def _key(params):
    return hashlib.md5(json.dumps(params,sort_keys=True).encode()).hexdigest()[:16]

def fetch(reporter,period,partner,cmd,flow,pause=2.5,tries=4):
    """Returns (rows, status). status in {ok, empty, failed}. Cached on disk."""
    params=dict(reporterCode=reporter,period=period,partnerCode=partner,
                cmdCode=cmd,flowCode=flow)
    path=os.path.join(CACHE,_key(params)+".json")
    if os.path.exists(path):
        with open(path) as f: blob=json.load(f)
        STATS["cache_hit"]+=1
        return blob["rows"],blob["status"]
    url=BASE+"?"+"&".join(f"{k}={v}" for k,v in params.items())
    last=None
    for attempt in range(tries):
        try:
            r=urllib.request.Request(url,headers={"User-Agent":UA})
            with urllib.request.urlopen(r,timeout=60) as f:
                d=json.loads(f.read())
            rows=d.get("data") or []
            status="ok" if rows else "empty"
            if len(rows)>=ROW_CAP:
                status="capped"; STATS["capped"]+=1
            STATS["fetched"]+=1
            if status=="empty": STATS["empty"]+=1
            with open(path,"w") as f:
                json.dump({"params":params,"rows":rows,"status":status},f)
            time.sleep(pause)
            return rows,status
        except urllib.error.HTTPError as e:
            last=f"HTTP {e.code}"
            if e.code in (429,500,502,503):
                STATS["throttled"]+=1
                time.sleep(pause*(3**attempt))   # back off hard on throttle
                continue
            break
        except Exception as e:
            last=str(e); time.sleep(pause*(2**attempt)); continue
    STATS["error"]+=1
    # Do NOT cache failures as empty - that would silently become "no trade".
    print(f"    !! FAILED {params} -> {last}",flush=True)
    return [],"failed"

def dedupe(rows):
    """Collapse to one row per (cmdCode,partnerCode,flowCode,refYear)."""
    out={}
    for r in rows:
        k=(r.get("cmdCode"),r.get("partnerCode"),r.get("flowCode"),r.get("refYear"))
        out.setdefault(k,r)
    return list(out.values())
