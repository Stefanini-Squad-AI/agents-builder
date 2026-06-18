# SPEC: Artifact Grouping

**Feature ID:** W-ART-GROUP
**Status:** Planned
**Depends on:** Existing `ProjectArtifact`, `ArtifactKind`, extractors, `ProjectContext`, `render_project_context()`

---

## 1. Objective

Allow users to categorize uploaded artifacts into exactly 3 semantic groups so that:

1. LLM prompts receive **structured, purpose-labeled context** instead of a flat artifact list -- improving skill naming, coverage analysis, and card drafting.
2. The UI presents artifacts with **clear semantic intent** (what this artifact is *for*, not just its file format).
3. Groups are **user-assigned** at upload time and reassignable afterward -- no auto-discovery or MCP population.

---

## 2. Groups

| Enum value | Display label | Purpose |
|------------|--------------|---------|
| `code_to_migrate` | Code to be Migrated | Legacy source code, ETL packages, config files that are the *input* to a migration or modernization effort. |
| `architectural_standards` | Architectural Standards | Design docs, coding standards, security policies, ADRs -- artifacts that define *constraints and patterns* the output must conform to. |
| `other_topics` | Other Topics | Everything else: meeting notes, glossaries, reference material, business rules not yet classified. |

These 3 groups are **fixed**. No custom groups, no dynamic extension.
---

## 3. Domain Model

### 3.1 New enum: `ArtifactGroup`

Add to `packages/core/app/enums.py`:

`python
class ArtifactGroup(StrEnum):
    CODE_TO_MIGRATE = "code_to_migrate"
    ARCHITECTURAL_STANDARDS = "architectural_standards"
    OTHER_TOPICS = "other_topics"
`

### 3.2 Column on `project_artifacts`

Add to `ProjectArtifact` in `packages/core/app/domain/projects.py`:

`python
artifact_group: Mapped[str] = mapped_column(
    String(32),
    nullable=False,
    server_default=ArtifactGroup.OTHER_TOPICS.value,
)
`

Add CHECK constraint to `__table_args__`:

`python
CheckConstraint(
    f"artifact_group IN ({values_csv(ArtifactGroup)})",
    name="artifact_group_valid",
),
`

**Why a column, not a separate table:** Each artifact belongs to exactly one group. A column is simpler, avoids a join, and matches the existing `kind` column pattern.

### 3.3 Default value

`server_default="other_topics"` ensures:
- Existing rows migrate cleanly (all ungrouped artifacts land in "Other Topics").
- Uploads that omit the group field get a sensible default.

---

## 4. Pydantic Schema Changes

### 4.1 `ArtifactSummary` -- add `artifact_group`

In `packages/core/app/schemas/views.py`:

`python
class ArtifactSummary(BaseModel):
    model_config = _VIEW_CONFIG
    id: UUID
    filename: str
    kind: ArtifactKind
    artifact_group: ArtifactGroup          # NEW
    extraction_status: ExtractionStatus
    size_bytes: int
    content_md_excerpt: str | None = None
    content_md_truncated: bool = False
`

### 4.2 `ProjectContext` -- replace flat list with grouped dict

`python
class ProjectContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: str
    qa: dict[str, str] = {}
    tech_choices_by_dimension: dict[str, list[TechChoiceView]] = {}
    artifact_groups: dict[str, list[ArtifactSummary]] = {}   # NEW -- replaces artifact_summaries
    context_notes_md: str = ""
`

**Migration note:** `artifact_summaries: list[ArtifactSummary]` is removed. All consumers must use `artifact_groups` instead.
---

## 5. API Changes

### 5.1 Upload: add `artifact_group` form field

In `packages/core/app/api/artifacts.py`, `upload_artifact()`:

`python
async def upload_artifact(
    project_ref: str,
    file: Annotated[UploadFile, File(..., description="Binary upload")],
    kind: Annotated[str, Form(...)] = ArtifactKind.DOC.value,
    artifact_group: Annotated[str, Form(...)] = ArtifactGroup.OTHER_TOPICS.value,  # NEW
    session: Session = Depends(get_session),
) -> ArtifactSummary:
`

Validate `artifact_group` the same way `kind` is validated:

`python
try:
    group_enum = ArtifactGroup(artifact_group)
except ValueError:
    raise HTTPException(
        status_code=422,
        detail=f"artifact_group must be one of {[g.value for g in ArtifactGroup]}",
    ) from None
`

Set on the ORM row:

`python
row = ProjectArtifact(
    ...
    artifact_group=group_enum.value,
)
`

### 5.2 New endpoint: reassign group

`python
@router.patch(
    "/api/artifacts/{artifact_id}/group",
    response_model=ArtifactSummary,
)
def reassign_artifact_group(
    artifact_id: uuid.UUID,
    body: ReassignGroupRequest,
    session: Session = Depends(get_session),
) -> ArtifactSummary:
    """Move an artifact to a different group without re-uploading."""
`

Request schema:

`python
class ReassignGroupRequest(BaseModel):
    artifact_group: ArtifactGroup
`

### 5.3 `_to_summary()` update

The helper in `artifacts.py` must include `artifact_group`:

`python
def _to_summary(row: ProjectArtifact) -> ArtifactSummary:
    excerpt = None
    if row.content_md:
        excerpt = row.content_md[:2000]
    return ArtifactSummary(
        id=row.id,
        filename=row.filename,
        kind=ArtifactKind(row.kind),
        artifact_group=ArtifactGroup(row.artifact_group),   # NEW
        extraction_status=ExtractionStatus(row.extraction_status),
        size_bytes=row.size_bytes,
        content_md_excerpt=excerpt,
        content_md_truncated=row.content_md_truncated,
    )
`

### 5.4 Endpoint summary

| Method | Endpoint | Change |
|--------|----------|--------|
| POST | `/api/projects/{ref}/artifacts` | Add `artifact_group` form field |
| GET | `/api/projects/{ref}/artifacts` | Response includes `artifact_group` per artifact |
| GET | `/api/artifacts/{id}` | Response includes `artifact_group` |
| PATCH | `/api/artifacts/{id}/group` | **New** -- reassign group |
| POST | `/api/artifacts/{id}/retry` | No change |
| DELETE | `/api/artifacts/{id}` | No change |
---

## 6. Service Layer Changes

### 6.1 `ProjectContextService.load_project_context()`

In `packages/core/app/services/project_context_service.py`:

**Before:**
`python
artifact_summaries = []
for artifact in project.artifacts:
    if artifact.extraction_status == "extracted":
        summary = ArtifactSummary(...)
        artifact_summaries.append(summary)

return ProjectContext(
    ...
    artifact_summaries=artifact_summaries,
    ...
)
`

**After:**
`python
artifact_groups: dict[str, list[ArtifactSummary]] = {
    g.value: [] for g in ArtifactGroup
}
for artifact in project.artifacts:
    if artifact.extraction_status == "extracted":
        excerpt = None
        if artifact.content_md:
            excerpt = artifact.content_md[:2000]
            if len(artifact.content_md) > 2000:
                excerpt += "..."

        summary = ArtifactSummary(
            id=artifact.id,
            filename=artifact.filename,
            kind=artifact.kind,
            artifact_group=ArtifactGroup(artifact.artifact_group),
            extraction_status=artifact.extraction_status,
            size_bytes=artifact.size_bytes,
            content_md_excerpt=excerpt,
            content_md_truncated=artifact.content_md_truncated,
        )
        group_key = artifact.artifact_group
        artifact_groups.setdefault(group_key, []).append(summary)

return ProjectContext(
    ...
    artifact_groups=artifact_groups,
    ...
)
`

### 6.2 `render_context_string()` update

Same grouping logic applied to the service's own render method.
---

## 7. Context Rendering

### 7.1 `render_project_context()` in `context_helpers.py`

**Before:**
`python
if context.artifact_summaries:
    parts.append("**Uploaded Documents:**")
    for artifact in context.artifact_summaries:
        ...
`

**After:**
`python
GROUP_LABELS = {
    "code_to_migrate": "Code to be Migrated",
    "architectural_standards": "Architectural Standards",
    "other_topics": "Other Topics",
}

if context.artifact_groups:
    for group_key, artifacts in context.artifact_groups.items():
        if not artifacts:
            continue
        label = GROUP_LABELS.get(group_key, group_key)
        parts.append(f"**{label}:**")
        for artifact in artifacts:
            excerpt = artifact.content_md_excerpt or "No content extracted"
            truncated_note = " (truncated)" if artifact.content_md_truncated else ""
            parts.append(f"- **{artifact.filename}** ({artifact.kind}): {excerpt}{truncated_note}")
        parts.append("")
`

### 7.2 `render_project_context_compact()` update

`python
if context.artifact_groups:
    total = sum(len(arts) for arts in context.artifact_groups.values())
    non_empty = len([g for g in context.artifact_groups.values() if g])
    parts.append(f"Artifacts: {total} files in {non_empty} groups")
`

### 7.3 Rendered output example

`
## Project Context

**Objective**: Migrate legacy SSIS packages to Databricks

**Code to be Migrated:**
- **etl_customer_load.dtsx** (code): SSIS package extracting customer data...
- **legacy_orders.py** (code): Python 2.7 order processing script...

**Architectural Standards:**
- **coding_standards.md** (doc): Company-wide Python coding standards...
- **security_policy.pdf** (doc): Information security requirements...

**Other Topics:**
- **meeting_notes.md** (doc): Kickoff meeting notes from 2024-01-15...
`

Empty groups are omitted entirely.
---

## 8. Prompt Impact

### 8.1 No structural changes to prompt classes

All 5 prompts (`ProposeSkillSet`, `DraftSkillBody`, `ProposeBacklog`, `DraftCard`, `SuggestTechStack`) receive `ProjectContext` and delegate rendering to `render_project_context()`. The grouped rendering flows through automatically.

### 8.2 Expected quality improvements

| Prompt | How grouping helps |
|--------|-------------------|
| **ProposeSkillSet** | "Code to be Migrated" group -> better analyzer skill names (e.g. `legacy-ssis-analyzer`). "Architectural Standards" -> context skills that encode constraints. |
| **DraftSkillBody** | Skill body can reference specific artifact groups by name, producing more targeted resource content. |
| **ProposeBacklog** | Discovery/assessment phases draw from "Code to be Migrated"; compliance phases draw from "Architectural Standards". |
| **DraftCard** | Card inputs are clearer: a migration card references code artifacts; a standards-review card references standards artifacts. |
| **SuggestTechStack** | "Architectural Standards" artifacts may mention mandated or prohibited technologies, improving tech suggestions. |

---

## 9. Extraction Tools Per Group

No new extractors are needed. The existing 6 extractors already cover all file types across all groups:

| Group | Typical file types | Extractors |
|-------|-------------------|------------|
| `code_to_migrate` | .py, .java, .cs, .sql, .cbl, .xml, .json, .yaml, .dtsx | `CodeExtractor`, `SSISExtractor` |
| `architectural_standards` | .md, .pdf, .docx, .txt | `MarkdownExtractor`, `PdfExtractor`, `DocxExtractor` |
| `other_topics` | any | All (auto-selected by registry) |

The grouping is **semantic** (user intent), not **technical** (file format). The extractor registry (`select_extractor()`) dispatches on `(mime_type, ext)` regardless of group.
---

## 10. UI Changes

### 10.1 TypeScript types

In `packages/web/src/lib/api/types.ts`:

`	ypescript
export enum ArtifactGroup {
  CODE_TO_MIGRATE = "code_to_migrate",
  ARCHITECTURAL_STANDARDS = "architectural_standards",
  OTHER_TOPICS = "other_topics",
}

export interface ArtifactSummary {
  id: string;
  filename: string;
  kind: ArtifactKind;
  artifact_group: ArtifactGroup;           // NEW
  extraction_status: ExtractionStatus;
  size_bytes: number;
  content_md_excerpt?: string;
  content_md_truncated: boolean;
}

export interface ProjectContext {
  objective: string;
  qa: Record<string, string>;
  tech_choices_by_dimension: Record<string, TechChoiceView[]>;
  artifact_groups: Record<string, ArtifactSummary[]>;   // replaces artifact_summaries
  context_notes_md: string;
}
`

### 10.2 Upload form: group selector

Add a Select dropdown before the dropzone with 3 items:
- "Code to be Migrated" (value: code_to_migrate)
- "Architectural Standards" (value: architectural_standards)
- "Other Topics" (value: other_topics)

Pass artifact_group in the FormData when calling the upload endpoint.

### 10.3 Artifact list: group badge + reassign

Add a "Group" column with a colored badge (blue/purple/gray).
Clicking the badge opens a dropdown to reassign (calls PATCH endpoint).

### 10.4 New components

| Component | File | Purpose |
|-----------|------|---------|
| ArtifactGroupBadge | components/artifacts/artifact-group-badge.tsx | Colored badge + click-to-reassign dropdown |
| ArtifactGroupSelect | components/artifacts/artifact-group-select.tsx | Select dropdown for upload form |

### 10.5 API client

Add reassignGroup method to artifact API endpoints.
Add useReassignGroup TanStack Query mutation to use-artifacts.ts.---

## 11. Alembic Migration

File: packages/core/alembic/versions/<timestamp>_add_artifact_group_column.py

    def upgrade():
        op.add_column(
            "project_artifacts",
            sa.Column(
                "artifact_group",
                sa.String(32),
                nullable=False,
                server_default="other_topics",
            ),
        )
        op.execute(
            "ALTER TABLE project_artifacts ADD CONSTRAINT artifact_group_valid "
            "CHECK (artifact_group IN ('code_to_migrate','architectural_standards','other_topics'))"
        )

    def downgrade():
        op.execute("ALTER TABLE project_artifacts DROP CONSTRAINT artifact_group_valid")
        op.drop_column("project_artifacts", "artifact_group")

---

## 12. Implementation Order

1. Enum (ArtifactGroup) + Alembic migration
2. ORM column on ProjectArtifact + CHECK constraint
3. Pydantic schema changes (ArtifactSummary.artifact_group, ProjectContext.artifact_groups)
4. API: upload form field + _to_summary() update + reassign endpoint
5. Service: ProjectContextService.load_project_context() grouping logic
6. Context rendering: render_project_context() + render_project_context_compact()
7. TypeScript types + API client + TanStack Query hooks
8. UI components: ArtifactGroupBadge, ArtifactGroupSelect
9. UI integration: upload form, artifact list, reassign dropdown

---

## 13. Acceptance Criteria

- [ ] ArtifactGroup enum has exactly 3 values: code_to_migrate, architectural_standards, other_topics
- [ ] project_artifacts.artifact_group column exists with CHECK constraint and default other_topics
- [ ] Existing rows migrated with artifact_group = 'other_topics'
- [ ] POST /api/projects/{ref}/artifacts accepts artifact_group form field
- [ ] Upload defaults to other_topics when artifact_group is omitted
- [ ] GET /api/projects/{ref}/artifacts returns artifact_group per artifact
- [ ] PATCH /api/artifacts/{id}/group reassigns group, returns updated artifact
- [ ] ProjectContext.artifact_groups is a dict keyed by group value
- [ ] render_project_context() emits group-sectioned markdown (empty groups omitted)
- [ ] All 5 prompts receive grouped artifact context via render_project_context()
- [ ] UI upload form shows group selector with 3 options
- [ ] UI artifact list shows group badge with color coding
- [ ] UI group badge is clickable to reassign
- [ ] TypeScript ArtifactGroup enum matches Python enum values

---

## 14. File Structure Summary

    packages/core/app/
      enums.py                          # ArtifactGroup added
      domain/projects.py                # ProjectArtifact.artifact_group added
      schemas/views.py                  # ArtifactSummary + ProjectContext changes
      api/artifacts.py                  # upload form field + reassign endpoint
      services/project_context_service.py  # grouping logic
      prompts/context_helpers.py        # group-sectioned rendering
      alembic/versions/
        xxxx_add_artifact_group_column.py

    packages/web/src/
      lib/api/types.ts                  # ArtifactGroup enum + ArtifactSummary change
      lib/api/endpoints/artifacts.ts    # reassignGroup method
      lib/api/queries/use-artifacts.ts  # useReassignGroup mutation
      components/artifacts/
        artifact-group-badge.tsx         # NEW
        artifact-group-select.tsx        # NEW
        artifact-upload.tsx              # group selector added
        artifact-list.tsx                # group badge column added
