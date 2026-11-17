#!/usr/bin/env bash
# One-shot local setup check for job-search-copilot.
#
# Everything this tool actually needs to run is deliberately gitignored -- the
# LinkedIn export names thousands of real people, the CV is personal, and
# config.yaml holds API keys. So a fresh clone has the code and none of the
# inputs, and `scan` fails on a missing file rather than telling you what to
# put where. This script says exactly what is missing and what to do about it.
#
#   bash setup_local.sh          check, install deps, create config.yaml
#   bash setup_local.sh --check  check only, install nothing
set -uo pipefail

cd "$(dirname "$0")" || exit 1
CHECK_ONLY=${1:-}
ok=1

say()  { printf '%s\n' "$*"; }
good() { printf '  \033[32mok\033[0m    %s\n' "$*"; }
bad()  { printf '  \033[31mmissing\033[0m %s\n' "$*"; ok=0; }
warn() { printf '  \033[33mnote\033[0m  %s\n' "$*"; }

say ""
say "job-search-copilot - local setup"
say "working in: $(pwd)"
say ""

# --- Python -------------------------------------------------------------
PY=$(command -v python3 || true)
if [ -z "$PY" ]; then
  bad "python3 not found on PATH"
else
  ver=$("$PY" -c 'import sys; print("%d.%d"%sys.version_info[:2])')
  good "python3 $ver ($PY)"
  # 3.14 is very new; some wheels (rapidfuzz, pypdf) may not have binaries yet
  # and will try to compile from source.
  case "$ver" in
    3.1[4-9]) warn "python $ver is new - if a dependency fails to build, a 3.12 venv is the quickest fix:
             python3.12 -m venv .venv && source .venv/bin/activate" ;;
  esac
fi

# --- Dependencies -------------------------------------------------------
say ""
say "dependencies"
if [ "$CHECK_ONLY" != "--check" ] && [ -n "$PY" ]; then
  "$PY" -m pip install -q -r requirements.txt 2>&1 | tail -3
fi
for mod in requests yaml dateutil; do
  if "$PY" -c "import $mod" 2>/dev/null; then good "$mod"; else bad "$mod (pip install -r requirements.txt)"; fi
done
if "$PY" -c "import bs4" 2>/dev/null; then good "beautifulsoup4 (optional)"
else warn "beautifulsoup4 absent - careers-page link fallback is skipped; everything else runs"; fi
if "$PY" -c "import docx" 2>/dev/null; then good "python-docx (optional)"
else warn "python-docx absent - needed only for a .docx CV"; fi
# NOT a bare `import pypdf`: on some installs that raises a pyo3 panic from a
# broken `cryptography`, which the loader works around. A plain import here
# would report "not installed" for a package that in fact reads PDFs fine.
if "$PY" -c "from jobsearch.resume import _import_pdf_reader; _import_pdf_reader()" 2>/dev/null
then good "pypdf (optional) - PDF CVs readable"
else warn "PDF CVs not readable here - export the CV to .txt or .docx instead"; fi

# --- config.yaml --------------------------------------------------------
say ""
say "config"
if [ -f config.yaml ]; then
  good "config.yaml"
elif [ "$CHECK_ONLY" = "--check" ]; then
  bad "config.yaml (cp config.example.yaml config.yaml)"
else
  cp config.example.yaml config.yaml
  good "config.yaml created from the example - add your API keys to it"
fi

# --- Inputs that are gitignored on purpose ------------------------------
say ""
say "inputs (all gitignored - they are not in the clone)"

shopt -s nullglob
cvs=(data/cv/*.pdf data/cv/*.docx data/cv/*.txt data/cv/*.md)
if [ ${#cvs[@]} -gt 0 ]; then
  good "CV: ${cvs[0]}"
else
  bad "no CV in data/cv/ - ATS scoring is skipped without one.
          mkdir -p data/cv && cp ~/path/to/your_cv.pdf data/cv/"
fi

conns=(data/Connections*.csv)
if [ ${#conns[@]} -gt 0 ]; then
  good "LinkedIn export(s): ${#conns[@]} file(s)"
else
  bad "no data/Connections*.csv - scan cannot run without it.
          LinkedIn - Settings & Privacy - Data Privacy - Get a copy of your data
          - Connections. Unzip and put Connections.csv in data/.
          If you have more than one export, list them OLDEST FIRST in
          config.yaml under connections_files."
fi
shopt -u nullglob

# --- Verdict ------------------------------------------------------------
say ""
if [ "$ok" = "1" ]; then
  say "Ready. Run:"
  say "    python3 cli.py scan --min-ats 40 --sort-by-ats"
  say ""
  say "Without API keys it still works: the Workday, Greenhouse, Workable,"
  say "SmartRecruiters and Personio feeds need no auth, and Workday carries"
  say "full job-description text, which is what ATS scoring needs."
else
  say "Not ready - fix the items marked 'missing' above, then re-run:"
  say "    bash setup_local.sh --check"
  exit 1
fi
