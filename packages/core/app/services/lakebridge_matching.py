"""Filename matching helpers for Lakebridge result integration.

Used to map analyzer/transpiler output files back to their source artifacts
or analyzer file-result records. Kept as pure functions so the matching
behaviour is unit-testable without a database or the CLI.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)


def match_filename(target: str, candidates: Iterable[str]) -> str | None:
    """Best-effort match ``target`` to one of ``candidates``.

    Tiered matching, from strict to lenient:
      1. Exact full-name match (case-insensitive).
      2. Exact stem match (filename without extension), only if unambiguous.
      3. Substring stem match, only if exactly one candidate qualifies.

    Returns the matching candidate string, or ``None`` if there is no
    confident match. Ambiguous matches (more than one candidate at the same
    tier) deliberately return ``None`` rather than guessing — this avoids the
    ``order.sql`` ↔ ``order_detail.sql`` class of mis-link.
    """
    cand_list = [c for c in candidates]
    if not cand_list:
        return None

    target_lower = target.lower()

    # 1. Exact full-name match.
    for candidate in cand_list:
        if candidate.lower() == target_lower:
            return candidate

    target_stem = Path(target).stem.lower()

    # 2. Exact stem match (unambiguous only).
    stem_matches = [c for c in cand_list if Path(c).stem.lower() == target_stem]
    if len(stem_matches) == 1:
        return stem_matches[0]
    if len(stem_matches) > 1:
        return None

    # 3. Substring stem match (unambiguous only).
    substring_matches = [
        c
        for c in cand_list
        if target_stem and (
            target_stem in Path(c).stem.lower() or Path(c).stem.lower() in target_stem
        )
    ]
    if len(substring_matches) == 1:
        return substring_matches[0]

    return None


def select_output_file(
    output_dir: Path,
    prefer_keywords: Sequence[str] = (),
) -> Path | None:
    """Pick the most likely result file from a CLI output directory.

    Selection order:
      1. A JSON file whose name contains one of ``prefer_keywords`` (checked
         in priority order).
      2. The first JSON file by sorted name (deterministic). Logs a warning
         when more than one JSON exists and none matched a keyword, since the
         choice is then ambiguous.
      3. The first non-JSON file by sorted name (with a warning).
      4. ``None`` if the directory is empty.
    """
    json_files = sorted(output_dir.glob("*.json"), key=lambda p: p.name.lower())

    if json_files:
        for keyword in prefer_keywords:
            kw = keyword.lower()
            for candidate in json_files:
                if kw in candidate.name.lower():
                    return candidate

        if len(json_files) > 1:
            log.warning(
                "lakebridge_ambiguous_output",
                chosen=json_files[0].name,
                candidates=[f.name for f in json_files],
            )
        return json_files[0]

    other_files = sorted(
        (f for f in output_dir.iterdir() if f.is_file()),
        key=lambda p: p.name.lower(),
    )
    if other_files:
        log.warning("lakebridge_no_json_output", chosen=other_files[0].name)
        return other_files[0]

    return None
