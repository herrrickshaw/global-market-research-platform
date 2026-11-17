#!/usr/bin/env python3
"""scrub_transcript_secrets.py — redact leaked credentials from Claude Code
session transcripts (~/.claude/projects) and from the cloud copies of them.

Why: the 2026-10-26 audit found 11 live keys (AWS, GitHub gho_, OpenAI x2, Groq,
HuggingFace, GCP, Apify, Adzuna, TwelveData, NVIDIA) in 14 transcript files.
claude_sessions_dropbox_backup.sh copies those files to Dropbox nightly with
`rclone copy` (never deletes), and the one-off full-home Google Drive backup
of 2026-09-23 holds them too. ROTATE THE KEYS FIRST — redaction only limits
further exposure; Dropbox/Drive version history still keeps old revisions.

No secret values live in this file (it is in the PUBLIC $HOME repo). Values are
discovered at run time from:
  1. trufflehog --no-verification (works after rotation, since dead keys are
     still matched by pattern), restricted to DETECTORS below;
  2. every value of length >= MIN_LEN in ~/.config/market-secrets/credentials.env
     (catches keys trufflehog has no detector for: FRED, Zotero, Groww ...);
  3. optional --secrets-file (one literal per line), e.g. old keys you saved;
  4. any PEM "-----BEGIN ... PRIVATE KEY-----" block (regex).
Replacement is `[REDACTED:<source>:<sha256[:8]>]` — JSON-safe characters only,
so .jsonl lines stay valid; every rewritten file is re-parsed before the
atomic replace, and a file that would break is left untouched and reported.

Default is a DRY RUN: nothing is written, nothing is uploaded.

  # dry run, local + all remotes
  python3 scripts/scrub_transcript_secrets.py
  # apply locally only
  python3 scripts/scrub_transcript_secrets.py --apply --local-only
  # apply locally and push the redacted versions over the cloud copies
  python3 scripts/scrub_transcript_secrets.py --apply
  # incremental pre-copy mode used by the nightly cron wrapper
  python3 scripts/scrub_transcript_secrets.py --apply --local-only \
      --since-stamp ~/.claude/.scrub_stamp --skipped-out /tmp/x.lst
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOME = Path.home()
PROJECTS = HOME / ".claude" / "projects"
CRED_ENV = HOME / ".config" / "market-secrets" / "credentials.env"
LOG = HOME / "scripts" / "scrub_transcript_secrets.log"  # *.log is gitignored
LEDGER = HOME / ".claude" / ".scrub_redacted.lst"
RCLONE = "/opt/homebrew/bin/rclone"
TRUFFLEHOG = shutil.which("trufflehog") or "/opt/homebrew/bin/trufflehog"
MIN_LEN = 12  # shorter literals are too likely to hit ordinary text

# Detector types that produced VERIFIED hits in the 2026-10-26 audit. The noisy
# unverified ones (Privacy, UnifyID, JDBC, Postgres templates) are left out on
# purpose; pass --detectors all to widen.
DETECTORS = "AWS,Github,OpenAI,Groq,HuggingFace,GCP,Apify,Adzuna,TwelveData,NVAPI"

# (local root, remote root, rclone excludes) — one-way copies that may hold transcripts.
REMOTES = [
    (PROJECTS, "dropbox:claude-memory-backup/projects", ["-Users-umashankar/memory/**"]),
    (PROJECTS / "-Users-umashankar" / "memory", "dropbox:claude-memory-backup/memory", []),
    (PROJECTS, "googledrive:umashankar-home-backup-2026-09-23/.claude/projects", []),
]

PEM_RE = re.compile(
    rb"-----BEGIN ([A-Z ]{0,20})PRIVATE KEY-----.*?-----END \1PRIVATE KEY-----", re.S)
TEXT_SUFFIXES = {".jsonl", ".json", ".txt", ".md", ".log", ".yaml", ".yml", ""}
SECRET_NAME_RE = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|PAT$|CREDENTIAL", re.I)
NOT_SECRET_NAME_RE = re.compile(r"USER(NAME)?$|EMAIL|MODEL|_URL$|_HOST$|_ID$(?<!KEY_ID)", re.I)
HITS: dict[str, int] = {}       # source -> matches (dry-run report)
HIT_FILES: dict[str, int] = {}  # source -> files


def inner_suffix(p: Path) -> str:
    """'.jsonl' for x.jsonl and x.jsonl.gz — cache_memory_cleaner gzips old transcripts."""
    return Path(p.stem).suffix if p.suffix == ".gz" else p.suffix


def is_text(p: Path) -> bool:
    return inner_suffix(p) in TEXT_SUFFIXES


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line)
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def tag(source: str, value: bytes) -> bytes:
    return f"[REDACTED:{source}:{hashlib.sha256(value).hexdigest()[:8]}]".encode()


def escaped_variants(s: str, depth: int = 3) -> set[str]:
    """The literal as it appears raw, JSON-escaped once (inside a .jsonl string),
    and escaped again (tool output that was itself JSON)."""
    out, cur = {s}, s
    for _ in range(depth - 1):
        cur = json.dumps(cur)[1:-1]
        out.add(cur)
    return out


# ---------------------------------------------------------------- discovery
def from_trufflehog(paths: list[Path], detectors: str) -> dict[str, str]:
    found: dict[str, str] = {}
    paths = [p for p in paths if p.exists()]
    for i in range(0, len(paths), 200):  # keep argv bounded in incremental mode
        cmd = [TRUFFLEHOG, "filesystem", *map(str, paths[i:i + 200]), "--json",
               "--no-verification", "--no-update", "--results=verified,unknown,unverified"]
        if detectors != "all":
            cmd.append(f"--include-detectors={detectors}")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode not in (0, 183):
            raise RuntimeError(f"trufflehog exit {r.returncode}: {r.stderr[-400:]}")
        for line in r.stdout.splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            det, raw, raw2 = rec.get("DetectorName", "?"), rec.get("Raw") or "", rec.get("RawV2") or ""
            vals = [raw]
            if raw2.startswith(raw) and len(raw2) > len(raw):
                vals.append(raw2[len(raw):].lstrip(":;|, "))  # e.g. AWS: RawV2 = "<id>:<secret>"
            elif raw2:
                vals.append(raw2)
            for v in list(vals):
                # GCP: Raw/RawV2 is a credential JSON trufflehog reassembles (never verbatim
                # in the file), so redact its key fields instead of the blob
                if v.lstrip().startswith("{"):
                    try:
                        blob = json.loads(v)
                        vals += [str(blob.get("private_key_id", "")), str(blob.get("private_key", ""))]
                        vals.remove(v)
                    except (json.JSONDecodeError, ValueError, AttributeError):
                        pass
            for v in vals:
                # a re-run sees our own tags inside reassembled JSON — never re-redact those
                if len(v) >= MIN_LEN and "[REDACTED:" not in v:
                    found[v] = det
    return found


def from_env_file(path: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    if not path.exists():
        return found
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, val = line.removeprefix("export ").split("=", 1)
        name, val = name.strip(), val.strip().strip("'\"")
        # Only secret-typed names: usernames, emails, model names and URLs in this
        # file matched ~85k harmless places in the 2026-10-26 dry run.
        if not SECRET_NAME_RE.search(name) or NOT_SECRET_NAME_RE.search(name):
            continue
        if len(val) >= MIN_LEN and not val.startswith(("/", "http://localhost", "~")):
            found[val] = f"env:{name}"
    return found


def from_secrets_file(path: Path | None) -> dict[str, str]:
    if not path:
        return {}
    return {l.strip(): "listed" for l in path.read_text().splitlines() if len(l.strip()) >= MIN_LEN}


def build_matcher(secrets: dict[str, str]):
    variants: dict[bytes, bytes] = {}
    for val, src in secrets.items():
        t = tag(src, val.encode())
        for v in escaped_variants(val):
            variants[v.encode()] = t
    if not variants:
        return None, variants
    # longest first so a key is never partially replaced by a shorter overlapping one
    pat = re.compile(b"|".join(re.escape(v) for v in sorted(variants, key=len, reverse=True)))
    return pat, variants


# ---------------------------------------------------------------- scrubbing
def valid(path: Path, data: bytes) -> bool:
    try:
        if inner_suffix(path) == ".jsonl":
            for ln in data.splitlines():
                if ln.strip():
                    json.loads(ln)
        elif inner_suffix(path) == ".json":
            json.loads(data)
        return True
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False


def scrub_bytes(path: Path, data: bytes, pat, variants) -> tuple[bytes, int]:
    n, per_src = 0, {}

    def sub(m):
        t = variants[m.group(0)]
        src = t[10:-1].rsplit(b":", 1)[0].decode()  # b"[REDACTED:<src>:<hash>]"
        per_src[src] = per_src.get(src, 0) + 1
        return t
    if pat is not None:
        data, n = pat.subn(sub, data)
    for src, k in per_src.items():
        HITS[src] = HITS.get(src, 0) + k
        HIT_FILES[src] = HIT_FILES.get(src, 0) + 1
    # PEM blocks: apply per line so a match can never straddle two JSON strings
    out, pem_n = [], 0
    for ln in data.splitlines(keepends=True):
        new, k = PEM_RE.subn(lambda m: tag("pem", m.group(0)), ln)
        if k and inner_suffix(path) == ".jsonl" and not valid(path, new):
            new, k = ln, 0
        out.append(new)
        pem_n += k
    return b"".join(out), n + pem_n


def scrub_tree(root: Path, files: list[Path], pat, variants, apply: bool,
               skip_active_min: float) -> tuple[list[Path], list[Path], list[Path]]:
    changed, skipped, broken = [], [], []
    now = time.time()
    for p in files:
        try:
            st = p.stat()
        except FileNotFoundError:
            continue
        if not p.is_file() or not is_text(p):
            continue
        data = p.read_bytes()
        gz = p.suffix == ".gz"
        if gz:
            try:
                data = gzip.decompress(data)
            except (OSError, EOFError):
                broken.append(p)
                continue
        new, n = scrub_bytes(p, data, pat, variants)
        if not n:
            continue
        if now - st.st_mtime < skip_active_min * 60:
            skipped.append(p)  # a live session may still be appending to it
            continue
        if not valid(p, new):
            broken.append(p)
            continue
        changed.append(p)
        log(f"{'redact' if apply else 'would redact'} {n:>4} in {p.relative_to(root)}")
        if apply:
            fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".scrub-")
            with os.fdopen(fd, "wb") as f:
                f.write(gzip.compress(new, mtime=int(st.st_mtime)) if gz else new)
            os.chmod(tmp, st.st_mode & 0o777)
            os.replace(tmp, p)
            os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))  # keep session ordering in /resume
    return changed, skipped, broken


def walk(root: Path, since: float | None) -> list[Path]:
    out = []
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = Path(dp) / fn
            try:
                if since is None or p.stat().st_mtime > since:
                    out.append(p)
            except FileNotFoundError:
                pass
    return out


# ---------------------------------------------------------------- remotes
def rclone(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run([RCLONE, *args, "--tpslimit", "8"], capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"rclone {args[0]} exit {r.returncode}: {r.stderr[-400:]}")
    return r


def handle_remote(local_root: Path, remote: str, excludes: list[str], redacted: set[Path],
                  secrets: dict[str, str], detectors: str, apply: bool) -> None:
    excl = [a for e in excludes for a in ("--exclude", e)]
    r = rclone("lsf", "-R", "--files-only", remote, *excl, check=False)
    if r.returncode:
        log(f"[{remote}] unreachable, skipped: {r.stderr.strip()[-200:]}")
        return
    remote_files = set(r.stdout.splitlines())
    rel_changed = {str(p.relative_to(local_root)) for p in redacted
                   if p.is_relative_to(local_root)}
    overwrite = sorted(rel_changed & remote_files)
    remote_only = sorted(f for f in remote_files
                         if not (local_root / f).exists() and is_text(Path(f)))
    log(f"[{remote}] {len(remote_files)} files; {len(overwrite)} to overwrite with redacted "
        f"local copy; {len(remote_only)} remote-only to scan")

    with tempfile.TemporaryDirectory(prefix="scrub-remote-") as td:
        os.chmod(td, 0o700)
        lst = Path(td) / "files.lst"
        if overwrite and apply:
            lst.write_text("\n".join(overwrite) + "\n")
            rclone("copy", str(local_root), remote, "--files-from", str(lst), "--ignore-times")
            log(f"[{remote}] uploaded {len(overwrite)} redacted files")
        if remote_only:
            dl = Path(td) / "dl"
            lst.write_text("\n".join(remote_only) + "\n")
            rclone("copy", remote, str(dl), "--files-from", str(lst))
            got = walk(dl, None)
            # pruned-locally files may hold keys no local file still has
            pat_all, variants_all = build_matcher({**secrets, **from_trufflehog([dl], detectors)})
            ch, _, br = scrub_tree(dl, got, pat_all, variants_all, apply, skip_active_min=0)
            for b in br:
                log(f"[{remote}] NOT redacted (would break JSON): {b.relative_to(dl)}")
            if ch and apply:
                lst.write_text("\n".join(str(p.relative_to(dl)) for p in ch) + "\n")
                rclone("copy", str(dl), remote, "--files-from", str(lst), "--ignore-times")
                log(f"[{remote}] uploaded {len(ch)} redacted remote-only files")


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    ap.add_argument("--local-only", action="store_true", help="do not touch cloud copies")
    ap.add_argument("--root", type=Path, default=PROJECTS)
    ap.add_argument("--detectors", default=DETECTORS, help="trufflehog detector list, or 'all'")
    ap.add_argument("--secrets-file", type=Path, help="extra literals to redact, one per line")
    ap.add_argument("--no-env-file", action="store_true", help=f"don't use {CRED_ENV}")
    ap.add_argument("--skip-active-min", type=float, default=15,
                    help="skip files modified in the last N minutes (live sessions)")
    ap.add_argument("--since-stamp", type=Path,
                    help="incremental: only files newer than this stamp; stamp advanced on success")
    ap.add_argument("--pending", type=Path, help="files skipped last run, re-checked this run")
    ap.add_argument("--skipped-out", type=Path,
                    help="write skipped/broken files (relative to root) here, for rclone --exclude-from")
    a = ap.parse_args()

    started = time.time()
    since = None
    if a.since_stamp and a.since_stamp.exists():
        since = float(a.since_stamp.read_text().strip() or 0)
    files = walk(a.root, since)
    if a.pending and a.pending.exists():
        files += [a.root / l for l in a.pending.read_text().splitlines() if l.strip()]
    files = sorted(set(files))
    log(f"start {'APPLY' if a.apply else 'DRY-RUN'} root={a.root} files={len(files)}"
        f"{' (incremental)' if since else ''}")

    secrets = {}
    secrets.update(from_trufflehog(files if since else [a.root], a.detectors))
    if not a.no_env_file:
        secrets.update(from_env_file(CRED_ENV))
    secrets.update(from_secrets_file(a.secrets_file))
    by_src: dict[str, int] = {}
    for s in secrets.values():
        by_src[s] = by_src.get(s, 0) + 1
    log(f"literals to redact: {len(secrets)} {dict(sorted(by_src.items()))}")
    pat, variants = build_matcher(secrets)

    changed, skipped, broken = scrub_tree(a.root, files, pat, variants, a.apply, a.skip_active_min)
    for p in skipped:
        log(f"skipped (active <{a.skip_active_min:g}min): {p.relative_to(a.root)}")
    for p in broken:
        log(f"NOT redacted (would break JSON): {p.relative_to(a.root)}")
    log(f"local: {len(changed)} files {'redacted' if a.apply else 'would be redacted'}, "
        f"{len(skipped)} skipped, {len(broken)} unsafe")
    for src in sorted(HITS, key=lambda k: -HITS[k]):
        log(f"  hits {HITS[src]:>6} in {HIT_FILES[src]:>4} files  {src}")

    held = sorted(str(p.relative_to(a.root)) for p in skipped + broken)
    if a.skipped_out:
        a.skipped_out.write_text("\n".join(held) + ("\n" if held else ""))
    if a.pending and a.apply:
        a.pending.write_text("\n".join(held) + ("\n" if held else ""))

    # Ledger of every file ever redacted (relative paths only), so a later run
    # without --local-only still overwrites the cloud copies of files an earlier
    # --local-only run already cleaned.
    done_before = {a.root / l for l in LEDGER.read_text().splitlines() if l.strip()} \
        if LEDGER.exists() and a.root == PROJECTS else set()
    if a.apply and changed and a.root == PROJECTS:
        with open(LEDGER, "a") as f:
            f.writelines(f"{p.relative_to(a.root)}\n" for p in changed)

    if not a.local_only:
        for local_root, remote, excl in REMOTES:
            if a.root == PROJECTS or local_root.is_relative_to(a.root):
                handle_remote(local_root, remote, excl, set(changed) | done_before,
                              secrets, a.detectors, a.apply)

    if a.apply and a.since_stamp and not broken:
        a.since_stamp.write_text(f"{started}\n")
    log("done")
    return 2 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
