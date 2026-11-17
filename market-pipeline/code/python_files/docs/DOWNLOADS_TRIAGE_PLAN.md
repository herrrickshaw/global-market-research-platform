# Downloads Triage Plan — DRAFT FOR APPROVAL

**Status: PROPOSAL ONLY — nothing has been moved or deleted.**
Scope: `~/Downloads` — 379 loose files (2.6 GB) + 3 data directories.
Standing hazards respected: this directory is TCC-protected (launchd jobs can't
read it) and was once wiped mid-run by a parallel session — which is exactly why
durable material should leave it.

## Composition (measured 2026-08-02)

| Category | Count / size | Examples |
|---|---|---|
| Research PDFs | ~273 PDFs (bulk of file count) | papers (Amihud-adjacent, entropy, PEAD), govt reports, annual reports |
| Office docs | 28 docx · 22 xlsx · 17 pptx | CBG/ethanol decks, TCO models, cover letters |
| Data dirs | `data/` 1.0 GB · `market_cache/` 332 MB · `code/` 140 MB | pipeline-adjacent working copies |
| Duplicates | 20 files matching " (N)" pattern | `TradeStat-Eidb-Export (1).xlsx`, … |
| Personal/financial | bank statements, payslips, tax PDFs, ID documents | `AcctStatement_*.xls`, `gpay_statement_*.pdf`, membership card |

## Proposed moves (by rule, not file-by-file)

### R1 — Research library → `~/reference/`  (biggest win for the 273 PDFs)
- `~/reference/papers/` — academic PDFs (entropy, finance, ML). Two are cited in
  `references.bib` with `~/Downloads` paths (Parker 2017, Jahangiri & Corazza 2026)
  → **bib notes updated in the same commit** as the move.
- `~/reference/govt-reports/` — ministry/PIB/FCI/PPAC/tender documents.
- `~/reference/books/` — the four framework books + CFA texts + textbook PDFs.
- Rationale: read-only material; safe from the Downloads wipe hazard; launchd
  jobs could finally read them if ever needed.

### R2 — Active consulting workstreams → `~/Documents/workstreams/<name>/`
- CBG/SATAT, ethanol/distillery, EV/TCO, trade/FDI decks and models
  (`CBG_*`, `India_EV_*`, `Bus_TCO_*`, `E20_*`, `India_Trade_*`, …).
- These are deliverables-in-progress; they belong with their workstream, not in
  an inbox. Mapping table to be confirmed with you before moving.

### R3 — Personal & financial → `~/Documents/personal-archive/` (LOCAL ONLY)
- Statements, payslips, tax filings, ID scans, membership cards.
- **Excluded from every git repo and from the Dropbox research mirror** (the
  mirror backs research data; personal documents shouldn't ride along without an
  explicit decision from you).

### R4 — Data directories → the pipeline's own storage
- `Downloads/data/` (1.0 GB) and `Downloads/market_cache/` (332 MB): diff against
  `~/market-pipeline` copies; anything identical is a stale duplicate → delete
  list; anything unique → merge into the pipeline tree (DuckDB where tabular,
  per repo convention).
- `Downloads/code/` (140 MB): the old pre-migration working tree — already
  superseded by `~/market-pipeline`; verify nothing unique (git status inside it)
  then propose deletion. **Note: one tracked-in-git file here
  (`Downloads/code/web/chapterdetail.html`) carries the gitleaks figmeta
  allowlist — if it moves, update `~/.gitleaks.toml` in the same commit.**

### R5 — Duplicates & junk → delete list (with a review file first)
- The 20 " (N)" duplicates where the original exists and hashes match.
- Installer debris (`FortiClient*.dmg`), one-off exports already re-downloadable.
- A `deletion_candidates.txt` with sizes/hashes is produced for your sign-off —
  nothing deleted until you approve the list itself.

## What stays in Downloads
Genuinely in-flight items (this week's tenders, active application PDFs). The
inbox stays an inbox — it just stops being an archive.

## Execution order (after your approval)
1. R1 (pure moves, zero risk) + bib path updates
2. R3 (moves, local only)
3. R5 review file → your sign-off → delete
4. R4 diff report → your sign-off → merge/delete
5. R2 mapping table → your sign-off → moves

**Approve rules individually** — e.g. "R1 and R3 yes, R4 show me the diff first"
is a perfectly good answer.
