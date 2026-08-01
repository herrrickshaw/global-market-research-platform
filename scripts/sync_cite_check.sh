#!/bin/sh
# Sync the canonical citation checker + bibliography into the central install
# that every repo's pre-commit hook calls (~/.local/share/cite_check/).
# Canonical source of truth: market-pipeline/code/python_files/{cite_check.py,references.bib}
set -e
SRC="$HOME/market-pipeline/code/python_files"
DST="$HOME/.local/share/cite_check"
mkdir -p "$DST"
cp "$SRC/cite_check.py" "$SRC/references.bib" "$DST/"
echo "cite_check synced: $DST (from $SRC)"
