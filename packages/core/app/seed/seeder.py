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

from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import register_models
from app.domain.backlog import Card, CardDep, CardInput, CardSkill, Phase
from app.domain.identity import Tenant, User
from app.domain.projects import Project, ProjectQaAnswer
from app.domain.skills import Skill, SkillResource
from app.domain.tech import ProjectTechChoice, TechDimension, TechItem
from app.defaults import DEFAULT_LLM_MODEL, DEFAULT_LLM_PROVIDER
from app.enums import (
    CardDepRelation,
    CardInputKind,
    CardStatus,
    CardTemplate,
    CardType,
    Grouping,
    Priority,
    ProjectStatus,
    SkillKind,
    SkillResourceLanguage,
    TechChoiceRole,
    TechChoiceSource,
    UserRole,
)

# Ensure every ORM module is loaded before any mapper is configured. The
# seeder uses Project, which has a string-referenced relationship to LlmRun
# (via Project.llm_runs); without LlmRun imported, mapper configuration
# raises InvalidRequestError when the first query fires.
register_models()

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


# ---------------------------------------------------------------------------
# Reference PoC seeding (Step 0.8)
# ---------------------------------------------------------------------------


def seed_reference_pocs(session: Session, *, root: Path | None = None) -> dict[str, dict[str, int]]:
    """Load every reference project under `seed/reference/<slug>/`.

    Depends on the tech catalog already being loaded (so tech.yaml can
    reference catalog item slugs). The default tenant/user are created
    on-the-fly if absent.

    Idempotent at the project level: if a project with the same (tenant,
    slug) already exists, the call returns `{"already_present": 1}` for
    that PoC and does not touch it. To re-seed, drop the project row first.
    """
    src = root or (Path(__file__).parent / "reference")
    tenant, user = seed_default_tenant_and_user(session)
    seed_tech_catalog(session)  # ensure dimensions/items exist before tech.yaml lookups

    report: dict[str, dict[str, int]] = {}
    for project_dir in sorted(p for p in src.iterdir() if p.is_dir()):
        if project_dir.name.startswith("_") or project_dir.name == "__pycache__":
            continue
        report[project_dir.name] = _seed_one_project(session, project_dir, tenant, user)
    return report


def _read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _seed_one_project(
    session: Session, project_dir: Path, tenant: Tenant, user: User
) -> dict[str, int]:
    """Load one reference project from its directory into the DB."""
    proj_yaml = _read_yaml(project_dir / "project.yaml")
    slug = proj_yaml["slug"]

    existing = session.execute(
        select(Project).where(Project.tenant_id == tenant.id, Project.slug == slug)
    ).scalar_one_or_none()
    if existing is not None:
        return {"already_present": 1}

    project = Project(
        tenant_id=tenant.id,
        owner_user_id=user.id,
        slug=slug,
        name=proj_yaml["name"],
        objective=proj_yaml["objective"],
        context_md=proj_yaml.get("context_md"),
        card_code_prefix=proj_yaml["card_code_prefix"],
        card_template=proj_yaml.get("card_template", CardTemplate.PHASE_VLI.value),
        grouping=proj_yaml.get("grouping", Grouping.PHASE.value),
        status=proj_yaml.get("status", ProjectStatus.DRAFT.value),
        llm_provider=proj_yaml.get("llm_provider", DEFAULT_LLM_PROVIDER.value),
        llm_model=proj_yaml.get("llm_model", DEFAULT_LLM_MODEL),
    )
    session.add(project)
    session.flush()

    qa_count = _seed_qa(session, project, project_dir / "qa.yaml")
    tech_count = _seed_tech(session, project, project_dir / "tech.yaml", user)
    phase_by_code = _seed_phases(session, project, project_dir / "phases.yaml")
    skill_by_slug = _seed_skills(session, project, project_dir / "skills")
    card_count = _seed_cards(session, project, project_dir / "cards", phase_by_code, skill_by_slug)

    return {
        "qa_answers": qa_count,
        "tech_choices": tech_count,
        "phases": len(phase_by_code),
        "skills": len(skill_by_slug),
        "cards": card_count,
    }


def _seed_qa(session: Session, project: Project, qa_path: Path) -> int:
    if not qa_path.exists():
        return 0
    data = _read_yaml(qa_path) or {}
    n = 0
    for key, answer in data.items():
        if not isinstance(answer, str) or not answer.strip():
            continue
        session.add(
            ProjectQaAnswer(
                project_id=project.id,
                question_key=key,
                answer_md=answer.strip(),
            )
        )
        n += 1
    session.flush()
    return n


def _seed_tech(session: Session, project: Project, tech_path: Path, user: User) -> int:
    """Load tech.yaml picks into project_tech_choices.

    YAML shape:
        <dimension_slug>:
          - { item: <item_slug>, role: target|legacy|optional|must_avoid }
          - { custom: "Free form name", role: target, tags: [a, b] }   # user-added
          - { tbd: true }                                                # mark TBD
    """
    if not tech_path.exists():
        return 0
    data = _read_yaml(tech_path) or {}
    n = 0
    for dim_slug, picks in data.items():
        dim = session.execute(
            select(TechDimension).where(TechDimension.slug == dim_slug)
        ).scalar_one_or_none()
        if dim is None:
            continue
        for order_no, pick in enumerate(picks or []):
            role = pick.get("role", TechChoiceRole.TARGET.value)
            if pick.get("tbd"):
                session.add(
                    ProjectTechChoice(
                        project_id=project.id,
                        dimension_id=dim.id,
                        tech_item_id=None,
                        role=TechChoiceRole.TBD.value,
                        source=TechChoiceSource.CATALOG.value,
                        order_no=order_no,
                    )
                )
                n += 1
                continue
            if pick.get("custom"):
                custom_name = pick["custom"]
                custom_slug = _slugify(custom_name)
                item = session.execute(
                    select(TechItem).where(
                        TechItem.dimension_id == dim.id, TechItem.slug == custom_slug
                    )
                ).scalar_one_or_none()
                if item is None:
                    item = TechItem(
                        dimension_id=dim.id,
                        slug=custom_slug,
                        name=custom_name,
                        tags=list(pick.get("tags", []) or []),
                        is_custom=True,
                        created_by_user_id=user.id,
                    )
                    session.add(item)
                    session.flush()
                session.add(
                    ProjectTechChoice(
                        project_id=project.id,
                        dimension_id=dim.id,
                        tech_item_id=item.id,
                        role=role,
                        source=TechChoiceSource.USER_ADDED.value,
                        order_no=order_no,
                    )
                )
                n += 1
                continue
            item_slug = pick["item"]
            item = session.execute(
                select(TechItem).where(TechItem.dimension_id == dim.id, TechItem.slug == item_slug)
            ).scalar_one_or_none()
            if item is None:
                continue
            session.add(
                ProjectTechChoice(
                    project_id=project.id,
                    dimension_id=dim.id,
                    tech_item_id=item.id,
                    role=role,
                    source=TechChoiceSource.CATALOG.value,
                    order_no=order_no,
                )
            )
            n += 1
    session.flush()
    return n


def _seed_phases(session: Session, project: Project, phases_path: Path) -> dict[str, Phase]:
    """Insert phases in the order declared by phases.yaml."""
    out: dict[str, Phase] = {}
    if not phases_path.exists():
        return out
    data = _read_yaml(phases_path) or {}
    for order_no, phase_data in enumerate(data.get("phases", []) or []):
        phase = Phase(
            project_id=project.id,
            code=phase_data["code"],
            name=phase_data["name"],
            description_md=phase_data.get("description"),
            order_no=order_no,
        )
        session.add(phase)
        out[phase.code] = phase
    session.flush()
    return out


def _seed_skills(session: Session, project: Project, skills_dir: Path) -> dict[str, Skill]:
    """Insert skills (one .yaml per skill). Resources are inline under
    `resources: [{filename, language, content}, ...]`.
    """
    out: dict[str, Skill] = {}
    if not skills_dir.exists():
        return out
    for order_no, skill_file in enumerate(sorted(skills_dir.glob("*.yaml"))):
        data = _read_yaml(skill_file) or {}
        skill = Skill(
            project_id=project.id,
            slug=data["slug"],
            name=data["name"],
            description=data["description"],
            kind=_validate_enum(data["kind"], SkillKind, default=SkillKind.AUTHORING),
            body_md=data.get("body", ""),
            order_no=order_no,
        )
        session.add(skill)
        session.flush()
        out[skill.slug] = skill

        for r_idx, res in enumerate(data.get("resources", []) or []):
            session.add(
                SkillResource(
                    skill_id=skill.id,
                    filename=res["filename"],
                    content=res.get("content", ""),
                    language=_validate_enum(
                        res.get("language", "markdown"),
                        SkillResourceLanguage,
                        default=SkillResourceLanguage.MARKDOWN,
                    ),
                    order_no=r_idx,
                )
            )
    session.flush()
    return out


def _seed_cards(
    session: Session,
    project: Project,
    cards_dir: Path,
    phase_by_code: dict[str, Phase],
    skill_by_slug: dict[str, Skill],
) -> int:
    """Insert cards (one .yaml per card). Dependencies are resolved in a
    second pass so forward references between cards are allowed.
    """
    if not cards_dir.exists():
        return 0

    card_by_code: dict[str, Card] = {}
    deferred_deps: list[tuple[Card, list[str], list[str]]] = []

    files = sorted(cards_dir.glob("*.yaml"))
    for order_no, card_file in enumerate(files):
        data = _read_yaml(card_file) or {}
        phase = phase_by_code.get(data["phase_code"])
        if phase is None:
            continue

        card = Card(
            phase_id=phase.id,
            code=data["code"],
            title=data["title"],
            type=_validate_enum(data["type"], CardType, default=CardType.TASK),
            story_points=data.get("story_points"),
            priority=_optional_enum(data.get("priority"), Priority),
            status=_validate_enum(
                data.get("status", "draft"), CardStatus, default=CardStatus.DRAFT
            ),
            human_gate=bool(data.get("human_gate", False)),
            human_gate_checklist_md=data.get("human_gate_checklist"),
            context_md=data.get("context"),
            task_md=data.get("task"),
            outputs_md=data.get("outputs"),
            acceptance_criteria_md=data.get("acceptance_criteria"),
            order_no=order_no,
        )
        session.add(card)
        session.flush()
        card_by_code[card.code] = card

        for pos, skill_slug in enumerate(data.get("skills", []) or []):
            skill = skill_by_slug.get(skill_slug)
            if skill is not None:
                session.add(CardSkill(card_id=card.id, skill_id=skill.id, position=pos))

        for in_idx, ci in enumerate(data.get("inputs", []) or []):
            session.add(
                CardInput(
                    card_id=card.id,
                    kind=_validate_enum(
                        ci.get("kind", "external"),
                        CardInputKind,
                        default=CardInputKind.EXTERNAL,
                    ),
                    path=ci["path"],
                    label=ci.get("label"),
                    order_no=in_idx,
                )
            )

        deferred_deps.append(
            (
                card,
                list(data.get("depends_on", []) or []),
                list(data.get("parallel_with", []) or []),
            )
        )

    for card, deps, parallels in deferred_deps:
        for dep_code in deps:
            tgt = card_by_code.get(dep_code)
            if tgt is None:
                continue
            session.add(
                CardDep(
                    card_id=card.id,
                    depends_on_card_id=tgt.id,
                    relation=CardDepRelation.DEPENDS_ON.value,
                )
            )
        for par_code in parallels:
            tgt = card_by_code.get(par_code)
            if tgt is None:
                continue
            session.add(
                CardDep(
                    card_id=card.id,
                    depends_on_card_id=tgt.id,
                    relation=CardDepRelation.PARALLEL_WITH.value,
                )
            )

    session.flush()
    return len(card_by_code)


# ---------------------------------------------------------------------------
# Small parsing helpers
# ---------------------------------------------------------------------------


def _slugify(name: str) -> str:
    """Kebab-case `name`. Used for user-added tech items in tech.yaml."""
    import re

    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "item"


def _validate_enum(value: str, enum_cls: type[StrEnum], *, default: StrEnum) -> str:
    """Return value if it's a valid member of enum_cls, else `default.value`."""
    try:
        return str(enum_cls(value).value)
    except (ValueError, KeyError):
        return str(default.value)


def _optional_enum(value: str | None, enum_cls: type[StrEnum]) -> str | None:
    if value is None:
        return None
    try:
        return str(enum_cls(value).value)
    except (ValueError, KeyError):
        return None
