"""PDF extractor: markitdown primary, pdfplumber fallback.

Strategy:
  1. Try MarkItDown — fast, produces structured markdown when the PDF has
     a real text layer.
  2. If MarkItDown returns empty or trivial output (sometimes happens
     with scanned-style PDFs or unusual encodings), fall back to
     pdfplumber's per-page `extract_text()` and join with double-newlines.
  3. If both produce nothing, return a result with `error=` set explaining
     why; the row in `project_artifacts` will surface the message.
"""

from __future__ import annotations

from pathlib import Path

import pdfplumber
import structlog
from markitdown import MarkItDown

from app.extractors.base import ExtractionResult, Extractor, truncate_markdown

log = structlog.get_logger(__name__)

# "Trivial" = the markitdown output is shorter than this threshold AFTER
# stripping whitespace. Tuned for typical 1-page PDFs which should produce
# at least a few hundred characters of text.
_TRIVIAL_THRESHOLD = 40


class PdfExtractor(Extractor):
    name = "pdf"

    def can_handle(self, mime_type: str | None, ext: str) -> bool:
        if ext == "pdf":
            return True
        return bool(mime_type and mime_type.lower() == "application/pdf")

    def extract(self, path: Path) -> ExtractionResult:
        primary_text = self._try_markitdown(path)
        used = "markitdown"

        if not primary_text or len(primary_text.strip()) < _TRIVIAL_THRESHOLD:
            log.info(
                "pdf_markitdown_empty_falling_back",
                path=str(path),
                primary_chars=len(primary_text or ""),
            )
            fallback_text = self._try_pdfplumber(path)
            if fallback_text and len(fallback_text.strip()) > len(primary_text or ""):
                primary_text = fallback_text
                used = "pdfplumber"

        if not primary_text or not primary_text.strip():
            return ExtractionResult(
                content_md="",
                content_md_truncated=False,
                extractor_used=used,
                error="both markitdown and pdfplumber produced no text",
            )

        content, truncated = truncate_markdown(primary_text)
        return ExtractionResult(
            content_md=content,
            content_md_truncated=truncated,
            extractor_used=used,
        )

    def _try_markitdown(self, path: Path) -> str:
        try:
            md = MarkItDown()
            result = md.convert(str(path))
            return result.text_content or ""
        except Exception as e:
            log.warning("pdf_markitdown_error", path=str(path), error=str(e)[:200])
            return ""

    def _try_pdfplumber(self, path: Path) -> str:
        try:
            with pdfplumber.open(str(path)) as pdf:
                pages: list[str] = []
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    if text.strip():
                        pages.append(text)
                return "\n\n".join(pages)
        except Exception as e:
            log.warning("pdf_pdfplumber_error", path=str(path), error=str(e)[:200])
            return ""
