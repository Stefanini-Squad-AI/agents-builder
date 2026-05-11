"""Wrap a source-code file in a fenced markdown block.

The fence language is chosen from the file extension via a small
mapping. Unknown extensions fall back to ` ```text `, which keeps the
file readable in a markdown viewer without claiming a syntax.
"""

from __future__ import annotations

from pathlib import Path

from app.extractors.base import ExtractionResult, Extractor, truncate_markdown

# Maps lower-cased extension (no dot) to the fence language label.
_EXT_TO_LANG: dict[str, str] = {
    "py": "python",
    "pyi": "python",
    "ts": "typescript",
    "tsx": "tsx",
    "js": "javascript",
    "jsx": "jsx",
    "java": "java",
    "kt": "kotlin",
    "scala": "scala",
    "cs": "csharp",
    "sql": "sql",
    "cbl": "cobol",
    "cob": "cobol",
    "xml": "xml",
    "html": "html",
    "css": "css",
    "scss": "scss",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "ini": "ini",
    "cfg": "ini",
    "sh": "bash",
    "bash": "bash",
    "ps1": "powershell",
    "rs": "rust",
    "go": "go",
    "rb": "ruby",
    "php": "php",
    "swift": "swift",
    "lua": "lua",
    "pl": "perl",
    "r": "r",
    "m": "matlab",
    "cpp": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "c": "c",
    "h": "c",
    "hpp": "cpp",
    "dockerfile": "dockerfile",
}


class CodeExtractor(Extractor):
    """Last-resort extractor for source code files. Always wraps in a fence."""

    name = "code"

    def can_handle(self, mime_type: str | None, ext: str) -> bool:
        return ext in _EXT_TO_LANG

    def extract(self, path: Path) -> ExtractionResult:
        ext = path.suffix.lower().lstrip(".")
        lang = _EXT_TO_LANG.get(ext, "text")
        raw = path.read_text(encoding="utf-8", errors="replace")
        # Trailing newline keeps the closing fence on its own line.
        wrapped = f"```{lang}\n{raw.rstrip()}\n```\n"
        content, truncated = truncate_markdown(wrapped)
        return ExtractionResult(
            content_md=content,
            content_md_truncated=truncated,
            extractor_used=self.name,
        )
