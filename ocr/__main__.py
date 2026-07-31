"""
CLI for the Unlimited-OCR client.

    python3 -m ocr document.pdf                 # transcript to stdout
    python3 -m ocr scan.png -o out.md           # transcript to file
    python3 -m ocr --ping                       # check endpoint health

Run from the home directory (or with ~ on PYTHONPATH).
Requires UNLIMITED_OCR_URL — see ocr/serve/README.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ocr.unlimited_ocr import endpoint, is_configured, ocr_image, ocr_pdf, ping


def main() -> int:
    ap = argparse.ArgumentParser(prog='python3 -m ocr',
                                 description='OCR a PDF or image via a remote Unlimited-OCR endpoint')
    ap.add_argument('files', nargs='*', help='PDF or image files to transcribe')
    ap.add_argument('-o', '--output', help='write transcript here (single input only)')
    ap.add_argument('--ping', action='store_true', help='check endpoint reachability and exit')
    args = ap.parse_args()

    if args.ping:
        if not is_configured():
            print('UNLIMITED_OCR_URL not set (env or ~/.config/market-secrets/credentials.env)')
            return 1
        ok = ping()
        print(f'{endpoint()} -> {"reachable" if ok else "NOT reachable"}')
        return 0 if ok else 1

    if not args.files:
        ap.print_help()
        return 1
    if not is_configured():
        print('UNLIMITED_OCR_URL is not configured. See ocr/serve/README.md '
              'for how to start the GPU endpoint.', file=sys.stderr)
        return 1
    if args.output and len(args.files) > 1:
        print('-o only works with a single input file', file=sys.stderr)
        return 1

    for f in args.files:
        p = Path(f)
        text = ocr_pdf(p) if p.suffix.lower() == '.pdf' else ocr_image(p)
        if args.output:
            Path(args.output).write_text(text)
            print(f'wrote {args.output} ({len(text)} chars)')
        else:
            if len(args.files) > 1:
                print(f'===== {p.name} =====')
            print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
