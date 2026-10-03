"""Parse EIA dnav hist_xls workbooks into {series, title, unit, points[(date,value)]}.
Header position varies between workbooks, so locate the 'Date' cell rather than
assuming a fixed row."""
import xlrd,json,os,urllib.request,datetime

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
def download(series,freq,dest):
    url=f"https://www.eia.gov/dnav/pet/hist_xls/{series}{freq}.xls"
    if os.path.exists(dest) and os.path.getsize(dest)>0: return dest
    r=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(r,timeout=60) as f, open(dest,"wb") as o:
        o.write(f.read())
    return dest

def parse(path):
    b=xlrd.open_workbook(path); sh=b.sheet_by_index(1)
    hdr_r=hdr_c=None
    for r in range(min(12,sh.nrows)):
        for c in range(min(6,sh.ncols)):
            if str(sh.cell_value(r,c)).strip().lower()=="date":
                hdr_r,hdr_c=r,c; break
        if hdr_r is not None: break
    if hdr_r is None: raise ValueError("no Date header")
    title=str(sh.cell_value(hdr_r,hdr_c+1)).strip()
    pts=[]
    for r in range(hdr_r+1,sh.nrows):
        dv=sh.cell_value(r,hdr_c); vv=sh.cell_value(r,hdr_c+1)
        if dv=="" or vv=="" or not isinstance(vv,(int,float)): continue
        try:
            if isinstance(dv,float):
                y,m,d,*_=xlrd.xldate_as_tuple(dv,b.datemode)
                ds=f"{y:04d}-{m:02d}-{d:02d}"
            else: ds=str(dv)[:10]
        except Exception: continue
        pts.append([ds,float(vv)])
    unit="Thousand Barrels" if "Thousand Barrels" in title else ("Million Barrels" if "Million Barrels" in title else "")
    return {"title":title,"unit":unit,"points":pts}
