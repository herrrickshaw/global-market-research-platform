#!/bin/zsh
# Compress large local PDFs with ghostscript /ebook (150dpi — readable, big shrink).
# Safety: only replace the original if the output is a VALID pdf AND >=15% smaller.
# Skips cloud-synced folders and small PDFs (where /ebook doesn't help).
LOG=~/.ruflo/logs/pdf_compress.log
: > "$LOG"
export PATH="/opt/homebrew/bin:$PATH"

# wait for ghostscript to finish installing (up to ~5 min)
for i in {1..60}; do command -v gs >/dev/null && break; sleep 5; done
command -v gs >/dev/null || { echo "gs never became available" >> "$LOG"; exit 1; }

freed=0; done_n=0; skip=0
# only PDFs > 2MB (smaller ones rarely benefit)
find ~ -type f -iname "*.pdf" -size +2M 2>/dev/null \
  | grep -vE "/Library/|/\.git/|node_modules|/\.cache/|/\.Trash/|CloudStorage" \
  | while read f; do
      before=$(stat -f%z "$f" 2>/dev/null) || continue
      tmp="${f%.pdf}.__c.pdf"
      gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.5 -dPDFSETTINGS=/ebook \
         -dNOPAUSE -dQUIET -dBATCH -dDetectDuplicateImages=true \
         -sOutputFile="$tmp" "$f" 2>>"$LOG"
      if [ ! -s "$tmp" ]; then rm -f "$tmp"; skip=$((skip+1)); continue; fi
      after=$(stat -f%z "$tmp" 2>/dev/null)
      # validate the output opens, and is >=15% smaller
      if gs -o /dev/null -sDEVICE=nullpage "$tmp" >/dev/null 2>&1 \
         && [ "$after" -lt $((before * 85 / 100)) ]; then
        mv "$tmp" "$f"
        freed=$((freed + before - after))
        done_n=$((done_n+1))
        printf "  %6.1fMB -> %6.1fMB  %s\n" \
          $((before/1048576.0)) $((after/1048576.0)) "$(basename "$f")" >> "$LOG"
      else
        rm -f "$tmp"; skip=$((skip+1))   # not smaller enough or invalid — keep original
      fi
    done
echo "PDF_COMPRESS_DONE compressed=$done_n skipped=$skip freed_MB=$((freed/1048576))" >> "$LOG"
