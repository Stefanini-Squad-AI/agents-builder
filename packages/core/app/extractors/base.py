"""Extractor ABC + shared result type + truncation helper.

Every extractor produces an `ExtractionResult` so the caller (the Dramatiq
artifact actor in Step 0.11) can write a uniform set of columns on
`project_artifacts` without per-format branching.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

# Truncation thresholds. content_md is mirrored into Postgres TEXT; we
# cap it so a single huge upload cannot blow out the column or the
# downstream prompt-context budget. The original file always stays on
# disk in full.
TRUNCATION_THRESHOLD_BYTES = 1_000_000  # 1 MB
TRUNCATION_KEEP_HEAD_BYTES = 500_000
TRUNCATION_KEEP_TAIL_BYTES = 500_000


@dataclass(frozen=True)
class ExtractionResult:
    """Output of every extractor.

    `content_md`           : markdown payload, already truncated.
    `content_md_truncated` : True iff truncation was applied.
    `extractor_used`       : tag for `project_artifacts.extractor_used`.
    `error`                : non-None for partial failures (extractor
                              succeeded with caveats). True hard failures
                              raise instead of returning a result.
    """

    content_md: str
    content_md_truncated: bool
    extractor_used: str
    error: str | None = None


def truncate_markdown(content: str) -> tuple[str, bool]:
    """Apply the head-and-tail truncation rule.

    If `content` is under the threshold, returns it unchanged. Otherwise
    keeps the head 500 KB and tail 500 KB joined by a parseable marker
    that records the byte count omitted in the middle.

    Returns `(truncated_content, was_truncated)`.
    """
    raw = content.encode("utf-8")
    if len(raw) <= TRUNCATION_THRESHOLD_BYTES:
        return content, False

    head = raw[:TRUNCATION_KEEP_HEAD_BYTES].decode("utf-8", errors="ignore")
    tail = raw[-TRUNCATION_KEEP_TAIL_BYTES:].decode("utf-8", errors="ignore")
    omitted = len(raw) - len(head.encode("utf-8")) - len(tail.encode("utf-8"))
    marker = f"\n\n[... truncated, {omitted} bytes omitted ...]\n\n"
    return f"{head}{marker}{tail}", True


class Extractor(ABC):
    """Base class for all extractors.

    Sub-classes declare a stable `name` (used as `extractor_used` on the
    DB row) and implement `can_handle()` + `extract()`.
    """

    name: str

    @abstractmethod
    def can_handle(self, mime_type: str | None, ext: str) -> bool:
        """Return True if this extractor accepts the given file.

        `ext` is the lower-cased extension without the leading dot.
        `mime_type` may be None when not provided by the upload metadata.
        """

    @abstractmethod
    def extract(self, path: Path) -> ExtractionResult:
        """Read `path` and produce an ExtractionResult.

        Implementations should call `truncate_markdown()` on their final
        text before constructing the result.
        """
