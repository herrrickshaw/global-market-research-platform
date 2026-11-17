"""Inline-SVG chart helpers. No external libraries: the Artifact CSP blocks
every remote host, so charts are hand-emitted SVG driven by real data."""

def _sc(v, lo, hi, a, b):
    if hi == lo: return (a + b) / 2
    return a + (v - lo) * (b - a) / (hi - lo)


def area_chart(points, width=760, height=230, pad_l=58, pad_b=26, pad_t=12, pad_r=14,
               accent="var(--accent)", fill="var(--accent-fade)", y_zero=False,
               label_every=None, unit="", series_id="c"):
    """points: [(iso_date, value)]. Emits area+line with faint grid and an
    emphasised endpoint dot."""
    if not points: return "<p class='empty'>no data</p>"
    xs = list(range(len(points)))
    ys = [p[1] for p in points]
    lo = 0 if y_zero else min(ys) * 0.97
    hi = max(ys) * 1.03
    x0, x1 = pad_l, width - pad_r
    y0, y1 = height - pad_b, pad_t

    def px(i): return _sc(i, 0, len(points) - 1, x0, x1)
    def py(v): return _sc(v, lo, hi, y0, y1)

    line = " ".join(f"{'M' if i == 0 else 'L'}{px(i):.1f},{py(v):.1f}"
                    for i, v in enumerate(ys))
    area = line + f" L{px(len(ys)-1):.1f},{y0:.1f} L{px(0):.1f},{y0:.1f} Z"

    # y grid: 4 ticks
    grid = []
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        y = py(v)
        grid.append(f"<line class='grid' x1='{x0}' y1='{y:.1f}' x2='{x1}' y2='{y:.1f}'/>")
        grid.append(f"<text class='ytick' x='{x0-8}' y='{y+3.5:.1f}'>{fmt_short(v)}</text>")

    # x labels: first, middle, last years
    idxs = [0, len(points) // 2, len(points) - 1]
    xlab = []
    for i in idxs:
        xlab.append(f"<text class='xtick' x='{px(i):.1f}' y='{height-8}'>{points[i][0][:4]}</text>")

    last_x, last_y = px(len(ys) - 1), py(ys[-1])
    return f"""<svg class="chart" viewBox="0 0 {width} {height}" role="img"
     aria-label="time series, latest {fmt_short(ys[-1])} {unit}">
  <g>{''.join(grid)}</g>
  <path d="{area}" fill="{fill}"/>
  <path d="{line}" fill="none" stroke="{accent}" stroke-width="1.6"/>
  <circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="3.4" fill="{accent}"/>
  <g>{''.join(xlab)}</g>
</svg>"""


def multi_line(series, width=760, height=250, pad_l=58, pad_b=26, pad_t=12, pad_r=110):
    """series: [(name, colorvar, [(date,value)])] sharing one y axis."""
    series = [s for s in series if s[2]]
    if not series: return "<p class='empty'>no data</p>"
    n = max(len(s[2]) for s in series)
    allv = [v for s in series for _, v in s[2]]
    lo, hi = min(allv) * 0.96, max(allv) * 1.04
    x0, x1 = pad_l, width - pad_r
    y0, y1 = height - pad_b, pad_t
    out, legend = [], []
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        y = _sc(v, lo, hi, y0, y1)
        out.append(f"<line class='grid' x1='{x0}' y1='{y:.1f}' x2='{x1}' y2='{y:.1f}'/>")
        out.append(f"<text class='ytick' x='{x0-8}' y='{y+3.5:.1f}'>{fmt_short(v)}</text>")
    for si, (name, col, pts) in enumerate(series):
        d = " ".join(f"{'M' if i==0 else 'L'}{_sc(i,0,len(pts)-1,x0,x1):.1f},"
                     f"{_sc(v,lo,hi,y0,y1):.1f}" for i, (_, v) in enumerate(pts))
        out.append(f"<path d='{d}' fill='none' stroke='{col}' stroke-width='1.6'/>")
        lx, lv = pts[-1]
        cy = _sc(lv, lo, hi, y0, y1)
        out.append(f"<circle cx='{x1:.1f}' cy='{cy:.1f}' r='3.2' fill='{col}'/>")
        legend.append(f"<text class='lgd' x='{x1+8}' y='{cy+3.5:.1f}' fill='{col}'>{name}</text>")
    pts0 = series[0][2]
    for i in [0, len(pts0)//2, len(pts0)-1]:
        out.append(f"<text class='xtick' x='{_sc(i,0,len(pts0)-1,x0,x1):.1f}' "
                   f"y='{height-8}'>{pts0[i][0][:4]}</text>")
    return f"<svg class='chart' viewBox='0 0 {width} {height}' role='img'>{''.join(out)}{''.join(legend)}</svg>"


def bar_chart(rows, width=760, bar_h=22, gap=7, pad_l=150, pad_r=90, pad_t=6,
              pos="var(--good)", neg="var(--crit)"):
    """rows: [(label, value)] - diverging horizontal bars around zero."""
    if not rows: return "<p class='empty'>no data</p>"
    height = pad_t * 2 + len(rows) * (bar_h + gap)
    vals = [v for _, v in rows]
    mx = max(abs(min(vals)), abs(max(vals))) or 1
    x0, x1 = pad_l, width - pad_r
    zero = x0 + (x1 - x0) * (0.5 if min(vals) < 0 else 0.0)
    if min(vals) >= 0: zero = x0
    out = [f"<line class='axis' x1='{zero:.1f}' y1='{pad_t}' x2='{zero:.1f}' y2='{height-pad_t}'/>"]
    for i, (lab, v) in enumerate(rows):
        y = pad_t + i * (bar_h + gap)
        w = abs(v) / mx * (x1 - zero if v >= 0 else zero - x0)
        bx = zero if v >= 0 else zero - w
        col = pos if v >= 0 else neg
        out.append(f"<rect x='{bx:.1f}' y='{y}' width='{max(w,1.2):.1f}' height='{bar_h}' fill='{col}' rx='1.5'/>")
        out.append(f"<text class='blab' x='{pad_l-10}' y='{y+bar_h*0.72:.1f}'>{lab}</text>")
        tx = (bx + w + 7) if v >= 0 else (bx - 7)
        anc = 'start' if v >= 0 else 'end'
        out.append(f"<text class='bval' x='{tx:.1f}' y='{y+bar_h*0.72:.1f}' text-anchor='{anc}'>{fmt_bn(v)}</text>")
    return f"<svg class='chart' viewBox='0 0 {width} {height}' role='img'>{''.join(out)}</svg>"


def fmt_short(v):
    a = abs(v)
    if a >= 1e9: return f"{v/1e9:.1f}B"
    if a >= 1e6: return f"{v/1e6:.0f}M"
    if a >= 1e3: return f"{v/1e3:.0f}k"
    return f"{v:.0f}"


def fmt_bn(v):
    return f"{'+' if v > 0 else ''}{v/1e9:,.1f}"
