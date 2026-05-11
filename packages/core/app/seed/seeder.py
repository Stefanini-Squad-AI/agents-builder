"""Idempotent seed loaders.

Public API:
- `load_tech_catalog_yaml(path)` -> parsed dict (pure data, no DB).
- `seed_tech_catalog(session)`   -> upsert dimensions + items from the YAML.
- `seed_default_tenant_and_user(session)` -> bootstrap the single-user MVP.

These functions are safe to call multiple times: existing rows are matched
by their natural keys (slug for dimensions; (dimension, slug) for items;
email for the user; name for the tenant). Re-runs only insert what's missing
and update nothing (slugs are stable; descriptions/tags can be edited later
via the API/UI rather than the seeder, to avoid clobbering user changes).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.identity import Tenant, User
from app.domain.tech import TechDimension, TechItem
from app.enums import UserRole

# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------


def load_tech_catalog_yaml(path: Path | None = None) -> dict[str, Any]:
    """Read the bundled `tech_catalog.yaml` (or an override path) into a dict.

    The returned shape matches the YAML file:
        {"dimensions": [{"slug": ..., "name": ..., "items": [...], ...}, ...]}
    """
    src = path or (Path(__file__).parent / "tech_catalog.yaml")
    with src.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict) or "dimensions" not in raw:
        raise ValueError(f"tech_catalog YAML at {src} is missing the top-level 'dimensions' key")
    return raw


# ---------------------------------------------------------------------------
# DB seeders
# ---------------------------------------------------------------------------


def _existing_dimensions_by_slug(session: Session) -> dict[str, TechDimension]:
    rows = session.execute(select(TechDimension)).scalars().all()
    return {row.slug: row for row in rows}


def _existing_items_by_slug(session: Session, dimension_id: Any) -> dict[str, TechItem]:
    rows = (
        session.execute(select(TechItem).where(TechItem.dimension_id == dimension_id))
        .scalars()
        .all()
    )
    return {row.slug: row for row in rows}


def seed_tech_catalog(session: Session, *, path: Path | None = None) -> dict[str, int]:
    """Idempotently insert dimensions + items from `tech_catalog.yaml`.

    Returns a small report: `{"dimensions_inserted": N, "items_inserted": M}`.
    Existing rows are left untouched (no descriptions/tags are overwritten).
    """
    raw = load_tech_catalog_yaml(path)
    dims_inserted = 0
    items_inserted = 0

    by_slug = _existing_dimensions_by_slug(session)

    for dim_yaml in raw.get("dimensions", []):
        slug = dim_yaml["slug"]
        if slug in by_slug:
            dim = by_slug[slug]
        else:
            dim = TechDimension(
                slug=slug,
                name=dim_yaml["name"],
                description=dim_yaml.get("description"),
                order_no=int(dim_yaml.get("order", 0)),
            )
            session.add(dim)
            session.flush()  # populate dim.id for FK below
            by_slug[slug] = dim
            dims_inserted += 1

        existing_items = _existing_items_by_slug(session, dim.id)
        for item_yaml in dim_yaml.get("items", []):
            item_slug = item_yaml["slug"]
            if item_slug in existing_items:
                continue
            session.add(
                TechItem(
                    dimension_id=dim.id,
                    slug=item_slug,
                    name=item_yaml["name"],
                    description=item_yaml.get("description"),
                    tags=list(item_yaml.get("tags", []) or []),
                    is_custom=False,
                )
            )
            items_inserted += 1

    session.flush()
    return {
        "dimensions_inserted": dims_inserted,
        "items_inserted": items_inserted,
    }


def seed_default_tenant_and_user(session: Session) -> tuple[Tenant, User]:
    """Bootstrap the single-user MVP: one Tenant and one User.

    Idempotent — looks up the existing rows by their natural keys before
    inserting. Returns the (Tenant, User) pair.
    """
    tenant = session.execute(select(Tenant).where(Tenant.name == "default")).scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(name="default")
        session.add(tenant)
        session.flush()

    user = session.execute(select(User).where(User.email == "local@workshop")).scalar_one_or_none()
    if user is None:
        user = User(
            email="local@workshop",
            name="Local",
            role=UserRole.OWNER.value,
        )
        session.add(user)
        session.flush()

    return tenant, user
