"""Convert a CSV file to a markdown table (with row cap).

Caps at `MAX_ROWS` to keep the LLM context payload bounded. When the cap
trips, a marker line indicates how many rows were omitted; the original
file always remains on disk in full.
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.extractors.base import ExtractionResult, Extractor, truncate_markdown

MAX_ROWS = 200


def _md_cell(value: str) -> str:
    """Escape pipe characters and collapse newlines so a value fits one cell."""
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


class CsvExtractor(Extractor):
    """Render CSV as a markdown table; cap at 200 rows."""

    name = "csv_to_md"

    def can_handle(self, mime_type: str | None, ext: str) -> bool:
        if ext == "csv":
            return True
        return bool(mime_type and mime_type.lower() in {"text/csv", "application/csv"})

    def extract(self, path: Path) -> ExtractionResult:
        with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as fh:
            # csv.Sniffer is unreliable on small samples; default to comma
            # and only fall back to tab when the first line has tabs but no
            # commas. Good enough for the MVP.
            sample = fh.readline()
            fh.seek(0)
            delimiter = "\t" if ("\t" in sample and "," not in sample) else ","
            reader = csv.reader(fh, delimiter=delimiter)
            rows = list(reader)

        if not rows:
            return ExtractionResult(
                content_md="*(empty CSV)*\n",
                content_md_truncated=False,
                extractor_used=self.name,
            )

        header, *data = rows
        n_cols = len(header)
        # Normalize every row to n_cols so the table renders cleanly even
        # if some rows are short.
        normalized = [
            [*(r + [""] * n_cols)[:n_cols]] if len(r) < n_cols else r[:n_cols] for r in data
        ]

        was_capped = len(normalized) > MAX_ROWS
        kept = normalized[:MAX_ROWS]
        omitted = len(normalized) - len(kept)

        # Build the markdown table.
        lines = []
        lines.append("| " + " | ".join(_md_cell(h) for h in header) + " |")
        lines.append("|" + "---|" * n_cols)
        for row in kept:
            lines.append("| " + " | ".join(_md_cell(v) for v in row) + " |")
        if was_capped:
            lines.append("")
            lines.append(f"*... {omitted} more row(s) omitted (cap {MAX_ROWS}) ...*")
        body = "\n".join(lines) + "\n"

        content, truncated_marker = truncate_markdown(body)
        # `content_md_truncated` is True if EITHER the row cap fired OR
        # the bytes-level truncation fired. Both narrow the context.
        return ExtractionResult(
            content_md=content,
            content_md_truncated=was_capped or truncated_marker,
            extractor_used=self.name,
        )
