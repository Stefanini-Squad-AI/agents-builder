"""Tests for the tech catalog YAML.

These tests load the YAML directly via PyYAML and validate the shape — they
do NOT touch SQLAlchemy. (The DB-level `seed_tech_catalog()` is exercised
in `test_seeder.py` via testcontainers in a later step.)

The 13-dimension / 76-item count comes from docs/SPEC.md section 13.2.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CATALOG_PATH = Path(__file__).parent.parent / "app" / "seed" / "tech_catalog.yaml"

EXPECTED_DIMENSION_SLUGS = {
    "languages",
    "backend_framework",
    "frontend_framework",
    "messaging",
    "database",
    "cloud_infra",
    "architecture_patterns",
    "observability",
    "security",
    "testing",
    "ai_automation",
    "legacy_modernized",
    "sector",
}


@pytest.fixture(scope="module")
def catalog() -> dict:
    with CATALOG_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_top_level_shape(catalog: dict) -> None:
    assert isinstance(catalog, dict)
    assert "dimensions" in catalog
    assert isinstance(catalog["dimensions"], list)


def test_thirteen_dimensions(catalog: dict) -> None:
    """Exactly the 13 dimensions enumerated in SPEC section 13.2."""
    slugs = {d["slug"] for d in catalog["dimensions"]}
    assert slugs == EXPECTED_DIMENSION_SLUGS, (
        f"missing: {EXPECTED_DIMENSION_SLUGS - slugs}  "
        f"unexpected: {slugs - EXPECTED_DIMENSION_SLUGS}"
    )


def test_every_dimension_has_required_fields(catalog: dict) -> None:
    for dim in catalog["dimensions"]:
        assert dim.get("slug")
        assert dim.get("name")
        assert "order" in dim and isinstance(dim["order"], int)
        assert "items" in dim and isinstance(dim["items"], list)
        assert len(dim["items"]) >= 1, f"dimension {dim['slug']} has no items"


def test_every_item_has_required_fields(catalog: dict) -> None:
    for dim in catalog["dimensions"]:
        for item in dim["items"]:
            assert item.get("slug")
            assert item.get("name")
            tags = item.get("tags", [])
            assert isinstance(tags, list), f"tags on {dim['slug']}/{item['slug']} must be a list"


def test_slugs_are_kebab_case(catalog: dict) -> None:
    """All slugs are kebab-case (lowercase + digits + hyphens + underscores)."""
    import re

    pat = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
    for dim in catalog["dimensions"]:
        assert pat.match(dim["slug"]), f"bad dim slug: {dim['slug']}"
        for item in dim["items"]:
            assert pat.match(item["slug"]), f"bad item slug: {dim['slug']}/{item['slug']}"


def test_item_slugs_unique_within_dimension(catalog: dict) -> None:
    for dim in catalog["dimensions"]:
        slugs = [it["slug"] for it in dim["items"]]
        assert len(slugs) == len(set(slugs)), f"duplicate item slug in {dim['slug']}: {slugs}"


def test_minimum_item_count(catalog: dict) -> None:
    """SPEC says >= 70 items; we ship ~76. Locking in >= 70 as a floor."""
    total = sum(len(d["items"]) for d in catalog["dimensions"])
    assert total >= 70, f"only {total} items in catalog; expected >= 70"


def test_languages_includes_core_set(catalog: dict) -> None:
    """Spot-check: the 'languages' dimension must include the SPEC-listed set."""
    lang_dim = next(d for d in catalog["dimensions"] if d["slug"] == "languages")
    expected_subset = {"python", "java", "javascript", "typescript", "sql"}
    item_slugs = {it["slug"] for it in lang_dim["items"]}
    assert expected_subset.issubset(item_slugs), (
        f"languages missing: {expected_subset - item_slugs}"
    )


def test_sector_includes_brazilian_segments(catalog: dict) -> None:
    """The 7 sectors from SPEC section 13.2 must all be present."""
    sector = next(d for d in catalog["dimensions"] if d["slug"] == "sector")
    item_slugs = {it["slug"] for it in sector["items"]}
    expected = {
        "financeiro",
        "automotivo",
        "energia",
        "varejo",
        "logistica-ferroviaria",
        "educacao",
        "telecom",
    }
    assert item_slugs == expected
