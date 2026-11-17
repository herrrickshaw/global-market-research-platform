"""Render ranked matches to CSV, Markdown, and a standalone HTML page."""
from __future__ import annotations

import csv
import html
from datetime import date
from pathlib import Path

from .models import Match


def _contact_lines(match: Match, limit: int = 3) -> list[str]:
    """Best people to approach at this company, recruiters first."""
    if not match.network:
        return []
    seen, picks = set(), []
    for pool in (match.network.hiring_contacts, match.network.senior_contacts,
                 match.network.connections):
        for c in pool:
            if c.url in seen:
                continue
            seen.add(c.url)
            picks.append(c)
            if len(picks) >= limit:
                return picks
    return picks


def to_csv(matches: list[Match], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["score", "ats_percent", "ats_missing", "ats_knockouts",
                    "role_fit", "network_score", "freshness", "company",
                    "title", "location", "source", "posted_at", "url",
                    "connections", "hiring_contacts", "top_contact",
                    "top_contact_title", "top_contact_url", "reasons"])
        for m in matches:
            picks = _contact_lines(m, 1)
            top = picks[0] if picks else None
            w.writerow([
                m.total,
                # Blank, not 0: the posting carried no description to score.
                m.ats_percent if m.ats_percent is not None else "",
                "; ".join(m.ats.missing[:10]) if m.ats else "",
                "; ".join(m.ats.knockouts) if m.ats else "",
                m.role_fit, m.network_score, m.freshness,
                m.job.company, m.job.title, m.job.location, m.job.source,
                m.job.posted_at or "", m.job.url,
                m.network.size if m.network else 0,
                len(m.network.hiring_contacts) if m.network else 0,
                top.name if top else "", top.position if top else "",
                top.url if top else "", "; ".join(m.reasons),
            ])
    return path


def to_markdown(matches: list[Match], path: str | Path, title: str = "Job matches") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", "", f"_Generated {date.today().isoformat()} — {len(matches)} matches_", ""]
    warm = [m for m in matches if m.has_warm_path]
    lines += [f"**{len(warm)} of {len(matches)} have a warm path through your network.**", ""]
    for i, m in enumerate(matches, 1):
        lines.append(f"## {i}. {m.job.title} — {m.job.company}")
        lines.append("")
        if m.ats_percent is not None:
            lines.append(f"- **ATS {m.ats_percent}% keyword match**"
                         + (f" — knockout: {'; '.join(m.ats.knockouts)}"
                            if m.ats.knockouts else ""))
            if m.ats.missing:
                lines.append(f"- Add to CV: {', '.join(m.ats.missing[:8])}")
        lines.append(f"- **Score** {m.total:.3f}  (fit {m.role_fit:.2f} · "
                     f"network {m.network_score:.2f} · fresh {m.freshness:.2f})")
        lines.append(f"- **Location** {m.job.location or 'n/a'} · **Source** {m.job.source}"
                     + (f" · **Posted** {m.job.posted_at}" if m.job.posted_at else ""))
        lines.append(f"- **Apply** {m.job.url}")
        picks = _contact_lines(m)
        if picks:
            lines.append("- **Warm intros**")
            for c in picks:
                lines.append(f"    - {c.name} — {c.position or 'n/a'} — {c.url}")
        lines.append(f"- _{'; '.join(m.reasons)}_")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def to_html(matches: list[Match], path: str | Path, title: str = "Job matches") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    e = html.escape
    rows = []
    for i, m in enumerate(matches, 1):
        picks = _contact_lines(m)
        contacts = "<br>".join(
            f'<a href="{e(c.url)}">{e(c.name)}</a> <span class="t">{e(c.position or "")}</span>'
            for c in picks) or '<span class="t">no connections</span>'
        warm = "warm" if m.has_warm_path else "cold"
        rows.append(f"""<tr class="{warm}">
<td class="n">{i}</td>
<td><b>{m.total:.3f}</b><div class="t">fit {m.role_fit:.2f} · net {m.network_score:.2f}{f" · ATS {m.ats_percent}%" if m.ats_percent is not None else " · no JD"}</div></td>
<td><a href="{e(m.job.url)}"><b>{e(m.job.title)}</b></a><div class="t">{e(m.job.source)}
{e(str(m.job.posted_at) if m.job.posted_at else '')}</div></td>
<td>{e(m.job.company)}</td>
<td>{e(m.job.location or '')}</td>
<td>{contacts}</td>
</tr>""")

    warm_n = sum(1 for m in matches if m.has_warm_path)
    path.write_text(f"""<!doctype html><meta charset="utf-8">
<title>{e(title)}</title>
<style>
:root{{color-scheme:light dark}}
body{{font:14px/1.5 system-ui,-apple-system,sans-serif;margin:2rem auto;max-width:1200px;padding:0 1rem}}
h1{{margin-bottom:.25rem}}
.sub{{opacity:.7;margin-bottom:1.5rem}}
table{{border-collapse:collapse;width:100%}}
th,td{{text-align:left;padding:.55rem .6rem;border-bottom:1px solid rgba(128,128,128,.28);vertical-align:top}}
th{{position:sticky;top:0;background:Canvas;border-bottom:2px solid rgba(128,128,128,.5)}}
.t{{font-size:12px;opacity:.65}}
.n{{opacity:.5}}
tr.warm{{background:rgba(46,160,67,.09)}}
a{{color:inherit}}
</style>
<h1>{e(title)}</h1>
<div class="sub">{date.today().isoformat()} · {len(matches)} matches ·
<b>{warm_n}</b> with a warm path (highlighted)</div>
<table><thead><tr><th></th><th>Score</th><th>Role</th><th>Company</th>
<th>Location</th><th>Warm intros</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>""", encoding="utf-8")
    return path
