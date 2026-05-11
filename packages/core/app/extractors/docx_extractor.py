"""DOCX extractor — delegates to MarkItDown.

MarkItDown's DOCX handler converts paragraphs / headings / lists / tables
to markdown reasonably well. We do not attempt a fallback for DOCX in
MVP; if MarkItDown fails the result carries an error and the row goes to
status='failed'. Users can retry later via `workshop artifact retry`.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import structlog
from markitdown import MarkItDown

from app.extractors.base import ExtractionResult, Extractor, truncate_markdown

log = structlog.get_logger(__name__)


class DocxExtractor(Extractor):
    name = "markitdown"

    _ACCEPTED_MIMES: ClassVar[set[str]] = {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    def can_handle(self, mime_type: str | None, ext: str) -> bool:
        if ext == "docx":
            return True
        return bool(mime_type and mime_type.lower() in self._ACCEPTED_MIMES)

    def extract(self, path: Path) -> ExtractionResult:
        try:
            md = MarkItDown()
            result = md.convert(str(path))
            text = result.text_content or ""
        except Exception as e:
            log.warning("docx_markitdown_error", path=str(path), error=str(e)[:200])
            return ExtractionResult(
                content_md="",
                content_md_truncated=False,
                extractor_used=self.name,
                error=str(e)[:200],
            )

        content, truncated = truncate_markdown(text)
        return ExtractionResult(
            content_md=content,
            content_md_truncated=truncated,
            extractor_used=self.name,
        )
