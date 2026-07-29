"""
Client for a remote Unlimited-OCR endpoint (baidu/Unlimited-OCR, arXiv:2606.23050).

The model needs an NVIDIA GPU, so it never runs on this Mac. Instead it is
served elsewhere (Colab / EC2 GPU) behind a vLLM OpenAI-compatible API, and
this module talks to it over HTTP. See ocr/serve/README.md for how to bring
the endpoint up and where to point it.

Configuration (either source, env wins):
  - env var UNLIMITED_OCR_URL, e.g. https://xyz.trycloudflare.com
  - UNLIMITED_OCR_URL=... line in ~/.config/market-secrets/credentials.env

Optional tuning env vars:
  - UNLIMITED_OCR_MODEL            (default: baidu/Unlimited-OCR)
  - UNLIMITED_OCR_PAGES_PER_CALL   (default: 8 — the model's R-SWA attention
                                    is built for many pages in one pass)
  - UNLIMITED_OCR_DPI              (default: 170)
  - UNLIMITED_OCR_TIMEOUT          (default: 600 seconds per call)

When UNLIMITED_OCR_URL is unset, is_configured() is False and callers should
skip OCR entirely — this module is always an opt-in enhancement, never a
required dependency.
"""
from __future__ import annotations

import base64
import io
import os
import re
from pathlib import Path
from typing import Optional

CRED_FILE = Path.home() / '.config' / 'market-secrets' / 'credentials.env'
DEFAULT_MODEL = 'baidu/Unlimited-OCR'
# Prompt form used by the upstream repo's own inference examples.
PROMPT = 'document parsing.'


def endpoint() -> Optional[str]:
    """Base URL of the vLLM server, or None if not configured."""
    url = os.environ.get('UNLIMITED_OCR_URL', '').strip()
    if not url and CRED_FILE.exists():
        for line in CRED_FILE.read_text().splitlines():
            m = re.match(r'^\s*(?:export\s+)?UNLIMITED_OCR_URL\s*=\s*["\']?([^"\'#\s]+)', line)
            if m:
                url = m.group(1)
                break
    # Placeholder values like <your-url> are truthy but not real — skip them.
    if not url or url.startswith('<'):
        return None
    return url.rstrip('/')


def is_configured() -> bool:
    return endpoint() is not None


def ping(timeout: float = 10.0) -> bool:
    """True if the endpoint is configured AND currently reachable."""
    base = endpoint()
    if not base:
        return False
    try:
        import requests
        r = requests.get(f'{base}/v1/models', timeout=timeout)
        return r.ok
    except Exception:
        return False


def _render_pdf(file_bytes: bytes, dpi: int) -> list[bytes]:
    """Rasterize each PDF page to PNG bytes."""
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise RuntimeError(
            'PyMuPDF is required to send PDFs to Unlimited-OCR: pip install pymupdf'
        ) from e
    pages = []
    with fitz.open(stream=file_bytes, filetype='pdf') as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            pages.append(pix.tobytes('png'))
    return pages


def _chat(image_pngs: list[bytes], timeout: float) -> str:
    """One chat-completions call with 1..N page images; returns the transcript."""
    import requests
    base = endpoint()
    if not base:
        raise RuntimeError('UNLIMITED_OCR_URL is not configured')
    content = [
        {'type': 'image_url',
         'image_url': {'url': 'data:image/png;base64,'
                              + base64.b64encode(png).decode()}}
        for png in image_pngs
    ]
    content.append({'type': 'text', 'text': PROMPT})
    payload = {
        'model': os.environ.get('UNLIMITED_OCR_MODEL', DEFAULT_MODEL),
        'messages': [{'role': 'user', 'content': content}],
        'temperature': 0.0,
        'max_tokens': 16384,
    }
    r = requests.post(f'{base}/v1/chat/completions', json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()['choices'][0]['message']['content']


def ocr_pdf_bytes(file_bytes: bytes) -> str:
    """
    OCR a whole PDF given as bytes. Pages are batched
    UNLIMITED_OCR_PAGES_PER_CALL at a time (the model transcribes many pages
    in a single forward pass); batch transcripts are joined with form feeds.
    """
    dpi = int(os.environ.get('UNLIMITED_OCR_DPI', '170'))
    per_call = max(1, int(os.environ.get('UNLIMITED_OCR_PAGES_PER_CALL', '8')))
    timeout = float(os.environ.get('UNLIMITED_OCR_TIMEOUT', '600'))
    pages = _render_pdf(file_bytes, dpi=dpi)
    chunks = []
    for i in range(0, len(pages), per_call):
        chunks.append(_chat(pages[i:i + per_call], timeout=timeout))
    return '\f'.join(chunks)


def ocr_pdf(path: str | Path) -> str:
    return ocr_pdf_bytes(Path(path).read_bytes())


def ocr_image(path: str | Path) -> str:
    """OCR a single image file (png/jpg)."""
    timeout = float(os.environ.get('UNLIMITED_OCR_TIMEOUT', '600'))
    return _chat([Path(path).read_bytes()], timeout=timeout)


def markdown_tables(text: str) -> list[list[list[str]]]:
    """
    Extract GitHub-style markdown tables from OCR output as lists of rows
    (header first), for feeding into existing table parsers.
    """
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('|') and s.endswith('|') and s.count('|') >= 2:
            cells = [c.strip() for c in s.strip('|').split('|')]
            if all(re.fullmatch(r':?-{2,}:?', c or '-') for c in cells):
                continue  # separator row
            current.append(cells)
        else:
            if len(current) >= 2:
                tables.append(current)
            current = []
    if len(current) >= 2:
        tables.append(current)
    return tables
