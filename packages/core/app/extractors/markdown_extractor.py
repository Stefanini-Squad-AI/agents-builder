"""Pass-through extractor for `.md` and `.txt` files."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.extractors.base import ExtractionResult, Extractor, truncate_markdown


class MarkdownExtractor(Extractor):
    """Reads markdown / plain-text files verbatim."""

    name = "markdown"

    _ACCEPTED_EXTS: ClassVar[set[str]] = {"md", "markdown", "txt", ""}
    _ACCEPTED_MIMES: ClassVar[set[str]] = {"text/markdown", "text/plain"}

    def can_handle(self, mime_type: str | None, ext: str) -> bool:
        if ext in self._ACCEPTED_EXTS:
            return True
        return bool(mime_type and mime_type.lower() in self._ACCEPTED_MIMES)

    def extract(self, path: Path) -> ExtractionResult:
        raw = path.read_text(encoding="utf-8", errors="replace")
        content, truncated = truncate_markdown(raw)
        return ExtractionResult(
            content_md=content,
            content_md_truncated=truncated,
            extractor_used=self.name,
        )
