# Operations Roster — learnings, decisions, open work

Companion to [`ERROR_REGISTER.md`](ERROR_REGISTER.md). The register records *what
broke*; this records *what to do about it* and *what we now know*.

**How to use it.** Section 1 is a backlog: every item has a next action and a
"done when" that can be checked, so any item can be picked up on its own without
re-deriving context. Section 2 is the decision log, including options rejected —
a decision without its discarded alternatives gets relitigated. Section 3 is the
part that actually reduces future incidents: recurring failure *shapes*, each
paired with the guard that would have caught it.

Last updated 2026-08-17. Register: **10 open, 26 fixed, 1 lost**.

---

## 1. Backlog

Priority is severity × blast radius, not age. S1 = silently wrong data or lost
deliverable; S2 = degraded; S3 = latent; S4 = cosmetic.

### Now — data correctness

| # | Item | Next action | Done when |
|---|---|---|---|
| E-029 | `KNOWN_QUIRKS` GBp→GBP `/100` on `.L` was calibrated for the OHLCV panel, but the price source moved to Cassandra `cmp`, which yfinance already reports in GBP | Gate the quirk on `price_source_is_panel`; re-run the bridge for `.L` names | A `.L` name's bridged P/E matches screener.in within tolerance, and the on-sentinel count is 0 |
| E-002 | `/api/live/fetch` fire-and-forgets `upsert_quotes` into the same `stock_quotes` row the nightly batch writes, no ordering guarantee | Either write live fetches to a separate table, or stamp `fetched_at` and refuse older writes | Two concurrent writers cannot leave a row older than the newest observation |
| E-005 | `industry` is null in the E-004 reconstruction, and industry drives the sector-relative comparison the screen exists to make | Re-collect industry from BSE/NSE XBRL (`nse_xbrl_results.py`) — no *local* source has it | `backtest_pe_anomalies` runs with non-null industry for ≥90% of the IN universe |

### Now — the thing that nearly cost 909 MB

| # | Item | Next action | Done when |
|---|---|---|---|
| E-032 | Two `cloud_backup.sh` copies exist. `~/scripts/` is canonical (hardcoded `TREES`, → `market-data-archive`); `repos/repo-data-dedup/` reads the SSOT manifest (→ `market-data-backup`). **Both run.** The manifest's own header says it exists to stop exactly this | Decide one owner. Either make `~/scripts/` read `datasets.py backup`, or retire it and move its extra trees into the manifest | `grep -c TREES= ~/scripts/cloud_backup.sh` is 0, **or** the repo-data-dedup copy is unscheduled — and one dry-run covers every tree |
| new | `datasets.conf` is untracked in git. It is now backed up (added 08-17) but has no history — a bad edit is unrecoverable and invisible | Decide whether a public repo is the right home; if not, a private gist or the credential store's directory | `git log` shows the manifest, or a documented alternative history exists |

### Next — monitoring that can actually fail

| # | Item | Next action | Done when |
|---|---|---|---|
| new | The ETL audit's `missing` and `sha_mismatch` checks are **vacuous**: the registry holds 0 batches / 0 files, so `scan` has never run. Two of three signals in the nightly alert cannot fail | Schedule `etl_registry.py scan` before `audit` | An audit reports `files_checked > 0`, and deleting a test file makes it FAIL |
| E-007 | `daily_research.sh` lacks the `caffeinate` power assertion added to `daily_mailer.sh` (E-010) — R1–R15 still exposed to suspend-stalling | Add `caffeinate -i -m -w "$$"`; the script was mid-run when this was first attempted | `pmset -g log` shows no sleep events inside an R1–R15 window |
| E-031 | Coverage, not the bridge, is the ceiling on de-imputation — IN/US/EU have usable fundamentals for only ~41% of each Cassandra universe | Widen `global_fundamentals` (EDINET/DART pipelines exist; India via XBRL) | `median_imputed` share drops below 40% for IN/US/EU |
| E-030 | Cassandra `UPDATE` is an upsert, so bridging a ticker absent from the instrument universe **creates** a partial row (pe/roe, no cmp/name) | Filter bridge writes against `instruments` before the `UPDATE` | Row count with `pe IS NOT NULL AND cmp IS NULL` is 0 |

### Later — accepted risk, revisit on trigger

| # | Item | Trigger to revisit |
|---|---|---|
| E-008 | Cassandra `SimpleStrategy` RF=1 — no replica, node loss is data loss. Correct at this scale | The moment it runs on more than one node |
| E-009 | `pmset wakepoweron 0:10AM` still aims at a job retired 2026-07-29; failed to power on at all on 08-04 | Any missed overnight run |
| E-004 | **LOST.** `IN_screener_only_backup.parquet` deleted 08-14, git holds only a 132-byte LFS pointer, absent from both clouds. Numeric core reconstructed from `global_fundamentals` | Nothing to do — recorded so it is never assumed present |

---

## 2. Decisions

Recorded with rejected alternatives, per the changelog convention.

**Warehouse lives in the cloud store, reached through one seam.** 34 references
across 32 files now go through `warehouse_paths.py` → `market_paths.resolve()`.
*Rejected:* a fallback to the old repo path — the copies still existed, so a
fallback would have quietly served month-old panels to a backtest that then
reported a confident number. Stopping loudly beats answering wrongly.
*Rejected:* a regex sweep — the sites differ in type (`str` vs `Path`), and a
flattened rewrite would have failed inside a backtest weeks later, not at edit
time.

**Untracking is half the migration.** Removing files from a working tree without
`git rm --cached` + `.gitignore` is what caused E-033: git kept insisting 94
files were missing and any `checkout` resurrected them. Order is now: verify
cloud → `git rm --cached` → gitignore → commit → *then* delete.

**Parquet mirror alongside the pg_dump, not instead of it.** 18,396 MB → 1,403 MB
(13.1×), queryable in place. *Rejected:* replacing the dump — a dump restores, a
parquet mirror answers questions; they are different jobs. *Rejected:* trusting
the writer's byte count — row counts are re-read *from the written file*, because
a short write that still parses is the failure that matters.

**Datastores stay on the host.** Compute is proven cloud-portable (Actions probe
reached yfinance IN/US, NSE bhavcopy and screener.in — 4/4). Postgres and
Cassandra did not move. *Rejected:* containerising a single-node RF=1 Cassandra —
risks the serving layer for no gain.

**Anchored excludes, deliberately.** `/ohlcv/**` protects the repo tree without
silencing the cache-rooted entries whose own root *is* `.../ohlcv`. Unanchored,
the fix would have disabled the upload it depends on.

---

## 3. Recurring failure shapes

The register lists incidents; these are the *shapes* they keep arriving in. Each
is paired with the check that turns it from a discovery into a caught error.

### System shapes

**Absence reads as success.** `etl_registry.audit()` does
`if not os.path.isdir(root): continue` — so deleting the panels made it *stop
auditing them* rather than fail. Same family as `|| continuing` hiding step
failures, and as an alert reporting `0 missing` when 0 files were checked.
→ *Guard:* a check that cannot fail is not a check. Assert the denominator —
`files_checked > 0`, `sources_checked == expected`.

**`sync` mirrors deletions, so a local restore is not a restore.** 75 files
deleted on 08-14 were mirrored away overnight; restoring them from git on 08-17
left the cloud short, and the audit's one-way check caught it only because the
diff count was *exactly* 75. → *Guard:* after any restore, re-verify the cloud
leg explicitly; never assume the mirror still holds what you just brought back.

**Two sources of truth converge on one path.** The manifest exists to prevent
this and is itself bypassed by the canonical script's hardcoded `TREES`.
→ *Guard:* when a value appears in two files, one must read the other. A path in
32 files cannot be moved — that was the real defect behind E-033, not the two
broken files.

**A migration is not done when the data moves.** It is done when every consumer,
every backup tree, every audit source and the tracking metadata move with it.
08-14 moved the data and left 32 consumers, 2 backup definitions and 2 registry
sources behind.

### Working-method shapes (mine, from this session)

**Validation and side effect in the same invocation.** Three times a guard fired
correctly and the chained command ran anyway — including a `gh api` PUT that
wrote an empty file to `main` after its assertion failed. → *Guard:* the side
effect must be in a branch the guard controls, not a `;` after it.

**Trusting tool output format instead of reading it.** Three wrong answers today
from grep patterns that did not match what the tool actually prints — most
sharply, a dry-run reporting `Deleted: 80 (files), 909.243 MiB` in its *summary*
while my per-file grep returned 0. Also `rclone lsl | tail -1` read as "newest"
(it is unordered), and `$?` after a pipe capturing `tail`'s status.
→ *Guard:* read the raw output once before writing a pattern against it; prefer
the tool's own summary line to a reconstructed count.

**Checking without the config's own exclusions.** A manual `rclone check` that
omitted the dataset's excludes reported **21,639** differences; the real answer
was **1**. The audit applies per-dataset excludes precisely so engineered
absences are not read as data loss. → *Guard:* replicate the real check's
configuration, or state plainly that you did not.

**Reporting a number without checking whether it is answerable.** "0 missing, 0
sha mismatches" is reassuring and meaningless when 0 files were examined.
→ *Guard:* before reporting a clean metric, confirm it *could* have been dirty.
