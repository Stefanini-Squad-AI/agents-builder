"""Artifact extractor registry.

Each extractor declares which `(mime_type, ext)` pairs it handles via
`can_handle()`. The registry below lists extractors in priority order;
`select_extractor()` returns the first match.

Format coverage in MVP (SPEC section 17.16 — core set):
  PDF, DOCX, MD/TXT, CSV, code files (.py / .ts / .java / .cs / .sql /
  .cbl / .xml / .json / .yaml plus a broader common list).

PPTX, XLSX, and OCR are deferred to P3+.
"""

from __future__ import annotations

from pathlib import Path

from app.extractors.base import (
    TRUNCATION_KEEP_HEAD_BYTES,
    TRUNCATION_KEEP_TAIL_BYTES,
    TRUNCATION_THRESHOLD_BYTES,
    ExtractionResult,
    Extractor,
    truncate_markdown,
)
from app.extractors.code_extractor import CodeExtractor
from app.extractors.csv_extractor import CsvExtractor
from app.extractors.docx_extractor import DocxExtractor
from app.extractors.markdown_extractor import MarkdownExtractor
from app.extractors.pdf_extractor import PdfExtractor

# Order: structured formats first; CodeExtractor last as it covers many
# extensions and would shadow more specific extractors if placed earlier.
EXTRACTORS: list[Extractor] = [
    MarkdownExtractor(),
    CsvExtractor(),
    PdfExtractor(),
    DocxExtractor(),
    CodeExtractor(),
]


class NoExtractorError(Exception):
    """Raised when no registered extractor matches the file."""


def select_extractor(filename: str, mime_type: str | None = None) -> Extractor:
    """Return the first extractor that accepts the given file.

    `filename` may include a directory; only the extension is consulted.
    `mime_type` is optional but lets text-y formats win when ext is empty.
    """
    ext = Path(filename).suffix.lower().lstrip(".")
    for extr in EXTRACTORS:
        if extr.can_handle(mime_type, ext):
            return extr
    raise NoExtractorError(f"No extractor handles file={filename!r} mime={mime_type!r} ext={ext!r}")


__all__ = [
    "EXTRACTORS",
    "TRUNCATION_KEEP_HEAD_BYTES",
    "TRUNCATION_KEEP_TAIL_BYTES",
    "TRUNCATION_THRESHOLD_BYTES",
    "ExtractionResult",
    "Extractor",
    "NoExtractorError",
    "select_extractor",
    "truncate_markdown",
]
