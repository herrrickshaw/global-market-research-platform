"""Load a resume as plain text from PDF, DOCX, TXT or Markdown.

Every parser is optional and imported lazily. A missing or broken one produces
a message naming the file, the format and the package to install -- not a
stack trace, and never an empty string, because an empty resume would score
0% against every job and read as "you match nothing" rather than "nothing was
read".
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".rst"}
SUPPORTED = TEXT_SUFFIXES | {".pdf", ".docx"}


class ResumeError(RuntimeError):
    """The resume could not be read. Always names the reason and the fix."""


def _import_pdf_reader():
    """Import pypdf, working around a broken `cryptography` install.

    pypdf pulls in a crypt provider at import time, which imports
    `cryptography`, whose Rust bindings fail on some systems (this container
    among them: `ModuleNotFoundError: _cffi_backend`, then a pyo3 panic). That
    failure has nothing to do with reading text -- it only gates *encrypted*
    PDFs -- yet it makes every PDF unreadable.

    So a failure that names the crypt chain is retried with the provider
    stubbed out. An encrypted PDF then fails later with a clear message, which
    is the correct trade: an unencrypted CV, which is nearly all of them, reads
    fine instead of being rejected for a dependency it never needed.
    """
    try:
        from pypdf import PdfReader
        return PdfReader
    except ImportError as exc:
        raise ResumeError(
            f"PDF support needs pypdf (`pip install pypdf`): {exc}. "
            f"Export the CV to .docx or .txt to avoid the dependency."
        ) from exc
    except BaseException as exc:
        # pyo3 raises PanicException, which inherits from BaseException, not
        # Exception -- so a plain `except Exception` never sees the very
        # failure this function exists to survive. Genuine interrupts are
        # re-raised untouched.
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        # The panic's message is just "Python API call failed" and its class
        # is "PanicException" -- neither names the culprit. The MODULE does
        # (pyo3_runtime), so it has to be part of the check.
        blame = (f"{type(exc).__module__}.{type(exc).__name__}: {exc}").lower()
        if not any(k in blame for k in ("cryptography", "_rust", "_cffi",
                                        "pyo3", "panic")):
            raise ResumeError(f"PDF support failed to load: {exc}") from exc
        import sys
        import types
        log.warning("pypdf's crypt provider is broken (%s); stubbing it out. "
                    "Encrypted PDFs will not open, plain ones read normally.",
                    type(exc).__name__)
        sys.modules.setdefault("pypdf._crypt_providers._cryptography",
                               types.ModuleType("pypdf._crypt_providers._cryptography"))
        try:
            from pypdf import PdfReader
            return PdfReader
        except BaseException as retry_exc:
            if isinstance(retry_exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise ResumeError(
                f"PDF support could not be loaded even with the crypt provider "
                f"stubbed: {retry_exc}. Export the CV to .docx or .txt."
            ) from retry_exc


def _read_pdf(path: Path) -> str:
    PdfReader = _import_pdf_reader()
    try:
        reader = PdfReader(str(path))
        if getattr(reader, "is_encrypted", False):
            raise ResumeError(
                f"{path.name} is encrypted. Remove the password, or export "
                f"the CV to .docx or .txt.")
        pages = [(p.extract_text() or "") for p in reader.pages]
    except ResumeError:
        raise
    except Exception as exc:
        raise ResumeError(f"cannot read {path.name}: {exc}") from exc
    return "\n".join(pages)


def _read_docx(path: Path) -> str:
    try:
        import docx
    except ImportError as exc:
        raise ResumeError(
            f"cannot read {path.name}: DOCX support needs python-docx "
            f"(`pip install python-docx`)"
        ) from exc
    try:
        doc = docx.Document(str(path))
    except Exception as exc:
        raise ResumeError(f"cannot read {path.name}: {exc}") from exc
    parts = [p.text for p in doc.paragraphs]
    # Many CVs put dates, employers and skills in tables, which are not in
    # `paragraphs`. Skipping them loses exactly the keywords an ATS looks for.
    for table in doc.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


def load_resume(path: str | Path) -> str:
    """Read a resume file to text. Raises ResumeError with an actionable message."""
    p = Path(path)
    if not p.exists():
        raise ResumeError(f"resume not found: {p}")
    suffix = p.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        text = p.read_text(encoding="utf-8", errors="replace")
    elif suffix == ".pdf":
        text = _read_pdf(p)
    elif suffix == ".docx":
        text = _read_docx(p)
    elif suffix == ".doc":
        raise ResumeError(
            f"{p.name}: legacy .doc is not supported. Save as .docx or .pdf.")
    else:
        raise ResumeError(
            f"{p.name}: unsupported format {suffix!r}; expected one of "
            f"{sorted(SUPPORTED)}")

    text = normalize(text)
    if len(text) < 200:
        # A PDF of scanned images extracts to almost nothing. Silently scoring
        # it would report 0% against every job -- a wrong answer that looks
        # like a real one.
        raise ResumeError(
            f"{p.name}: extracted only {len(text)} characters. If this is a "
            f"scanned or image-based PDF the text layer is missing; export a "
            f"text-based copy or paste the CV into a .txt file.")
    return text


def normalize(text: str) -> str:
    """Flatten the artefacts PDF and DOCX extraction leave behind."""
    text = text.replace("­", "")            # soft hyphens
    text = re.sub(r"[‐-―]", "-", text)  # unicode dashes
    text = re.sub(r"[‘’]", "'", text)
    text = re.sub(r"[“”]", '"', text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # de-hyphenate line breaks
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def find_resume(directory: str | Path = "data/cv") -> Path | None:
    """Pick the most recently modified resume in a directory, if any."""
    d = Path(directory)
    if not d.is_dir():
        return None
    files = [p for p in d.iterdir()
             if p.is_file() and p.suffix.lower() in SUPPORTED]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)
