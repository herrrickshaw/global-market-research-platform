#!/usr/bin/env python3
"""Command-line entry point for the warm-intro job scanner."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from jobsearch.config import load_config
from jobsearch.connections import load_connections
from jobsearch.dedupe import find_ambiguous_clusters, find_name_collisions, refresh_stats
from jobsearch.network import build_company_index, network_strength, top_companies
from jobsearch.pipeline import load_network, run
from jobsearch.targets import best_contacts, rank_targets
from jobsearch.report import to_csv, to_html, to_markdown


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)-7s %(name)s: %(message)s",
    )


def cmd_network(args) -> int:
    cfg = load_config(args.config)
    paths = args.connections or cfg.connections_files
    _, index, stats = load_network(paths)
    print(json.dumps(stats, indent=2, default=str))
    print(f"\nTop {args.top} companies by warm-path strength:\n")
    print(f"{'strength':>8}  {'conns':>5} {'hire':>4} {'senior':>6}  company")
    for net in top_companies(index, args.top):
        print(f"{network_strength(net):8.3f}  {net.size:5d} {len(net.hiring_contacts):4d} "
              f"{len(net.senior_contacts):6d}  {net.display_name}")
    return 0


def cmd_dedupe(args) -> int:
    cfg = load_config(args.config)
    paths = args.connections or cfg.connections_files
    merged, index, stats = load_network(paths)
    print(json.dumps(stats, indent=2, default=str))

    if len(paths) >= 2:
        print("\nChange between first and last export:")
        print(json.dumps(refresh_stats(load_connections(paths[0]),
                                       load_connections(paths[-1])), indent=2))

    clusters = find_ambiguous_clusters(merged)
    print(f"\nAmbiguous clusters needing human review: {len(clusters)}")
    for c in clusters[: args.top]:
        print(f"  {c['name']} @ {c['company']} ({c['count']} records)")
        for u in c["profiles"]:
            print(f"      {u}")

    collisions = find_name_collisions(merged)
    print(f"\nName collisions (distinct people, never merged): {len(collisions)}")
    for c in collisions[:5]:
        print(f"  {c['name']}: {', '.join(c['companies'][:4])}")

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(
            {"stats": stats,
             "ambiguous": [{k: v for k, v in c.items() if k != "records"} for c in clusters],
             "collisions": collisions}, indent=2, default=str), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


def cmd_targets(args) -> int:
    """Offline: rank companies in the network as targets, no job feed needed."""
    cfg = load_config(args.config)
    paths = args.connections or cfg.connections_files
    _, index, stats = load_network(paths)
    targets = rank_targets(index, cfg.profile, limit=args.top,
                           min_connections=args.min_connections)

    print(f"network: {stats['output_rows']:,} connections across {stats['companies']:,} companies")
    print(f"\nTop {len(targets)} target companies (sector fit x network x function density):\n")
    for i, t in enumerate(targets, 1):
        print(f"{i:3d}. {t.score:.3f}  {t.network.display_name}")
        print(f"       sector {t.sector_fit:.2f} · network {t.strength:.2f} · "
              f"function {t.function_density:.2f}  ({', '.join(t.reasons)})")
        for c in best_contacts(t.network):
            tag = "TALENT" if c in t.network.hiring_contacts else (
                  "SENIOR" if c in t.network.senior_contacts else "      ")
            print(f"       {tag}  {c.name[:30]:32s} {(c.position or '')[:44]:46s} {c.url}")
        print()

    if args.out:
        import csv as _csv
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="") as fh:
            w = _csv.writer(fh)
            w.writerow(["rank", "score", "sector_fit", "network", "function_density",
                        "company", "connections", "hiring_contacts", "senior_contacts",
                        "contact_name", "contact_title", "contact_url", "contact_type"])
            for i, t in enumerate(targets, 1):
                for c in best_contacts(t.network, limit=5):
                    ctype = ("talent" if c in t.network.hiring_contacts else
                             "senior" if c in t.network.senior_contacts else "peer")
                    w.writerow([i, t.score, t.sector_fit, t.strength, t.function_density,
                                t.network.display_name, t.network.size,
                                len(t.network.hiring_contacts), len(t.network.senior_contacts),
                                c.name, c.position, c.url, ctype])
        print(f"wrote {args.out}")
    return 0


def cmd_scan(args) -> int:
    cfg = load_config(args.config)
    if args.connections:
        cfg.connections_files = args.connections
    if args.top:
        cfg.top_n = args.top
    if args.min_score is not None:
        cfg.profile.min_score = args.min_score
    if getattr(args, "resume", None):
        cfg.resume_path = args.resume
    if getattr(args, "min_ats", None) is not None:
        cfg.min_ats = args.min_ats
    if getattr(args, "sort_by_ats", False):
        cfg.sort_by_ats = True

    matches, stats = run(cfg)
    print(json.dumps(stats, indent=2, default=str))

    out = Path(args.out or cfg.out_dir)
    to_csv(matches, out / "matches.csv")
    to_markdown(matches, out / "matches.md", title="Warm-intro job matches")
    to_html(matches, out / "matches.html", title="Warm-intro job matches")
    print(f"\nwrote {out}/matches.{{csv,md,html}}")

    print(f"\nTop {min(20, len(matches))} matches:\n")
    for i, m in enumerate(matches[:20], 1):
        warm = f"  [{m.network.size} conns]" if m.has_warm_path else ""
        # "--" not "0%": the posting carried no description to score against.
        ats = f"{m.ats_percent:>3d}%" if m.ats_percent is not None else "  --"
        print(f"{i:3d}. {m.total:.3f} ats {ats}  "
              f"{m.job.title[:48]:50s} {m.job.company[:22]:24s}{warm}")
    if stats.get("ats_unscored_no_jd"):
        print(f"\n{stats['ats_unscored_no_jd']} of {len(matches)} carry no "
              f"job-description text, so they show '--' rather than a score. "
              f"Apollo returns no JD text at all; Workday, Greenhouse, Workable "
              f"and the portal feeds do.")
    return 0


def cmd_ats(args) -> int:
    """Score the CV against a single job description."""
    from jobsearch.ats import score_resume
    from jobsearch.resume import ResumeError, find_resume, load_resume

    cfg = load_config(args.config)
    path = args.resume or cfg.resume_path or find_resume(cfg.resume_dir)
    if not path:
        print(f"no resume given and none found in {cfg.resume_dir}/ "
              f"(pass --resume, or drop a .pdf/.docx/.txt there)", file=sys.stderr)
        return 2
    try:
        resume = load_resume(path)
    except ResumeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    jd = sys.stdin.read() if args.jd == "-" else Path(args.jd).read_text(
        encoding="utf-8", errors="replace")

    m = score_resume(resume, jd, top_missing=args.top_missing)
    if not m.scored_against_jd:
        print("; ".join(m.notes), file=sys.stderr)
        return 2

    print(f"ATS keyword match: {m.percent}%   (resume: {path})\n")
    for k in m.knockouts:
        print(f"  KNOCKOUT  {k}")
    for n in m.notes:
        print(f"  note      {n}")
    if m.missing:
        print("\nAdd these to the CV, highest impact first:")
        for term in m.missing:
            print(f"  - {term}")
    if m.matched:
        print(f"\nAlready matched ({len(m.matched)}): "
              f"{', '.join(m.matched[:15])}")
    print("\nThis is a keyword model, not a judgement of fit: a low score "
          "means the CV does not use the JD's vocabulary.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="job-search-copilot", description=__doc__)
    p.add_argument("-c", "--config", default="config.yaml")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("network", help="analyse the connections graph")
    n.add_argument("--connections", nargs="*", help="export files, OLDEST FIRST")
    n.add_argument("--top", type=int, default=40)
    n.set_defaults(func=cmd_network)

    d = sub.add_parser("dedupe", help="merge/dedupe exports and report what changed")
    d.add_argument("--connections", nargs="*", help="export files, OLDEST FIRST")
    d.add_argument("--top", type=int, default=20)
    d.add_argument("--out", help="write a JSON report here")
    d.set_defaults(func=cmd_dedupe)

    t = sub.add_parser("targets", help="rank companies to work, offline (no job feed)")
    t.add_argument("--connections", nargs="*", help="export files, OLDEST FIRST")
    t.add_argument("--top", type=int, default=40)
    t.add_argument("--min-connections", type=int, default=2)
    t.add_argument("--out", help="write a CSV here")
    t.set_defaults(func=cmd_targets)

    s = sub.add_parser("scan", help="fetch jobs and rank them against your network")
    s.add_argument("--connections", nargs="*", help="export files, OLDEST FIRST")
    s.add_argument("--top", type=int)
    s.add_argument("--min-score", type=float)
    s.add_argument("--out", help="output directory")
    s.add_argument("--resume", help="CV file (.pdf/.docx/.txt/.md) for ATS scoring")
    s.add_argument("--min-ats", type=int,
                   help="drop matches scoring below this %% against the JD "
                        "(postings with no JD text are kept, not zeroed)")
    s.add_argument("--sort-by-ats", action="store_true",
                   help="rank by ATS score instead of the blended score")
    s.set_defaults(func=cmd_scan)

    a = sub.add_parser("ats", help="score your CV against one job description")
    a.add_argument("--resume", help="CV file; defaults to the newest in data/cv")
    a.add_argument("--jd", required=True,
                   help="job-description file, or '-' to read stdin")
    a.add_argument("--top-missing", type=int, default=15)
    a.set_defaults(func=cmd_ats)

    args = p.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
