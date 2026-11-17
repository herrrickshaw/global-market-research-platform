import json,os
HERE=os.path.dirname(os.path.abspath(__file__))
_d=json.load(open(os.path.join(HERE,"partnerAreas.json")))
_rows=_d.get("results") or _d
NAME={}; ISGROUP={}
for r in _rows:
    c=r.get("PartnerCode") or r.get("id")
    try: c=int(c)
    except: continue
    NAME[c]=r.get("PartnerDesc") or r.get("text")
    ISGROUP[c]=bool(r.get("isGroup"))
def name(code,default=None):
    try: code=int(code)
    except: return default or str(code)
    return NAME.get(code, default or f"code {code}")
def is_group(code):
    try: return ISGROUP.get(int(code),False)
    except: return False
