# SPEC: SSIS Parser Consolidation & Tiered Formatting

**Document ID:** SPEC-SSIS-PC-001  
**Status:** Draft  
**Last Updated:** 2026-05-29  
**Author:** Agents Development Team  

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Design Principles](#2-design-principles)
3. [Schema Enhancements](#3-schema-enhancements)
4. [Parser Enhancements](#4-parser-enhancements)
5. [Extractor to Formatter Refactor](#5-extractor-to-formatter-refactor)
6. [SSISPackage Persistence](#6-ssispackage-persistence)
7. [Tiered Formatting L1/L2/L3](#7-tiered-formatting-l1l2l3)
8. [Generator Enhancements](#8-generator-enhancements)
9. [Impact on StrategyClassifier](#9-impact-on-strategyclassifier)
10. [Frontend Changes](#10-frontend-changes)
11. [Testing Strategy](#11-testing-strategy)
12. [Migration Path](#12-migration-path)
13. [Risk Assessment](#13-risk-assessment)
14. [Summary of Changes](#14-summary-of-changes)

---

## 1. Problem Statement

### 1.1 Current Architecture: Three Independent Parse Passes

The SSIS extraction pipeline currently executes three independent parse passes over the same `.dtsx` XML source, each producing its own representation with no shared intermediate model:

```
.dtsx file
  |
  +--> Extractor  (720 lines)  --> Markdown summary (LLM context)
  |       Extracts: Script Task code, loop details,
  |                variable bindings, XML-decoded SQL
  |
  +--> Parser     (764 lines)  --> SSISPackage (Pydantic model)
  |       Discards: Script Task code, loop details,
  |                bindings, XML-decoded SQL
  |
  +--> Generator  (re-parses)  --> Python conversion artifacts
          Re-parses from disk, losing all Extractor knowledge
```

### 1.2 Extractor (720 lines)

The `SSISExtractor` in `extractors/ssis_extractor.py` performs direct XML manipulation to produce a human-readable markdown summary. It is the **only** component that extracts:

- **Script Task code** -- the full VSA/vbproj source code embedded in `<ScriptTaskProject>` elements
- **For Loop details** -- `InitExpression`, `EvalExpression`, `AssignExpression` attributes
- **ForEach Loop details** -- enumerator type, variable mappings (`ForEachVariableMapping`)
- **Variable bindings** -- parameter bindings and result bindings on Execute SQL Tasks
- **XML-decoded SQL** -- SQL statements with XML entities properly decoded

This information is rendered into a markdown string and passed directly to the LLM as context. It is **never persisted** and **never available** to downstream components.

### 1.3 Parser (764 lines)

The `SSISParser` in `parsers/ssis_parser.py` builds a `SSISPackage` Pydantic model from the same `.dtsx` XML. However, it **discards** every piece of information that the Extractor uniquely captures:

| Information | Extracted by Extractor | Captured by Parser |
|---|---|---|
| Script Task source code | Yes | **No** |
| For Loop expressions | Yes | **No** |
| ForEach Loop mappings | Yes | **No** |
| Parameter/Result bindings | Yes | **No** |
| XML-decoded SQL | Yes | **No** (raw XML entities remain) |
| Task names, types, SQL | Yes | Yes |
| Connections, variables | Yes | Yes |
| Precedence constraints | Yes | Yes |

The Parser's `Task` model has no fields for script code, loop details, or bindings. These are silently dropped during parsing.

### 1.4 Generator (re-parses from disk)

The `SSISGenerator` in `generators/ssis_generator.py` does not consume the `SSISPackage` model at all. Instead, it **re-opens and re-parses** the `.dtsx` file from disk using its own ad-hoc XML queries. This means:

- All Extractor knowledge is unavailable
- All Parser knowledge is unavailable
- Any parsing logic must be duplicated a third time
- Script Task code is lost entirely -- the Generator can only emit a placeholder comment

### 1.5 Consequences

1. **Script Task code is lost** -- The most complex, migration-critical code in an SSIS package (VBA/VB.NET scripts) is extracted by the Extractor for LLM context but never persisted. The Generator cannot reference it, and the Parser model has no field for it.

2. **Loop details are invisible to analysis** -- For Loop and ForEach Loop expressions are shown to the LLM in the Extractor markdown but never stored in the `SSISPackage` model. Strategy classification and code generation cannot use them.

3. **Bindings never reach the LLM** -- Parameter bindings and result bindings on Execute SQL Tasks are extracted and rendered by the Extractor but not captured in the Parser model. The Generator cannot produce parameterized queries.

4. **XML entities not decoded in Parser** -- The Parser stores raw SQL with XML entities. The LLM receives decoded SQL from the Extractor but the persisted model has undecoded SQL, causing inconsistency.

5. **Generator re-parses** -- The Generator opens the `.dtsx` file from disk and performs its own XML queries, duplicating parsing logic and losing all intermediate knowledge.

6. **No size tiering** -- The Extractor produces a single monolithic markdown summary regardless of package complexity. Large packages (500+ tasks) can produce summaries exceeding LLM context windows, while small packages waste tokens on verbose formatting.

---

## 2. Design Principles

### P1: Parse Once, Use Everywhere

The `.dtsx` file is parsed exactly **once** by the `SSISParser`, producing a single authoritative `SSISPackage` model. All downstream consumers -- the Extractor (now Formatter), the Generator, the StrategyClassifier -- read from this model. No component re-opens or re-parses the source XML.

### P2: Extractor Becomes Formatter

The `SSISExtractor` is refactored into an `SSISFormatter` that reads from a `SSISPackage` model and produces markdown. The Extractor's XML-parsing logic is removed; its formatting logic is preserved. The `SSISExtractor.extract()` method becomes a thin orchestrator: parse -> persist -> format.

### P3: Persist SSISPackage

The `SSISPackage` Pydantic model is persisted to the database as a JSONB column on the `ETLPackage` ORM model. This makes the full parsed representation available to any component at any time without re-parsing.

### P4: Tiered Formatting (L1/L2/L3)

The `SSISFormatter` produces markdown at three detail levels:

| Tier | Audience | Content | Typical Size |
|---|---|---|---|
| L1 | Strategy classification, package listing | Structure only | 200-500 tokens |
| L2 | Code generation (unfocused) | Structure + signatures | 500-2,000 tokens |
| L3 | Code generation (focused task) | Full detail for target task | 2,000-8,000 tokens |

### P5: Backward Compatible

All new schema fields have default values. Existing `SSISPackage` instances deserialize without error. The Extractor's markdown output format is preserved by the Formatter to maintain LLM prompt compatibility.

### P6: Idempotent Enrichment

Parser methods that enrich existing tasks (e.g., adding script info to a Script Task) are idempotent. Running them multiple times produces the same result. This allows incremental enrichment without side effects.

---

## 3. Schema Enhancements

### 3.1 New Pydantic Models

#### ScriptTaskInfo

```python
from pydantic import BaseModel, Field, computed_field


class ScriptTaskInfo(BaseModel):
    language: str = Field(
        description="Script language: VB, CSharp, or unknown"
    )
    entry_method: str = Field(
        description="Entry point method name (e.g., ScriptMain)"
    )
    code: str = Field(
        description="Full source code of the script entry point"
    )
    read_only_vars: list[str] = Field(
        default_factory=list,
        description="Variables available as read-only in the script"
    )
    read_write_vars: list[str] = Field(
        default_factory=list,
        description="Variables available as read-write in the script"
    )

    @computed_field
    @property
    def code_signature(self) -> str:
        """First line of code that is not blank, a comment, or an Import/Using statement."""
        for line in self.code.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("'") or stripped.startswith("//"):
                continue
            if stripped.lower().startswith(("imports ", "using ")):
                continue
            return stripped
        return ""

    @computed_field
    @property
    def code_char_count(self) -> int:
        """Character count of the full script code."""
        return len(self.code)
```

#### ForLoopDetails

```python
class ForLoopDetails(BaseModel):
    init_expression: str = Field(
        default="",
        description="Initialization expression (e.g., @Counter = 0)"
    )
    eval_expression: str = Field(
        default="",
        description="Evaluation expression (e.g., @Counter < 10)"
    )
    assign_expression: str = Field(
        default="",
        description="Assignment expression (e.g., @Counter = @Counter + 1)"
    )
```

#### ForEachVariableMapping

```python
class ForEachVariableMapping(BaseModel):
    variable: str = Field(
        description="SSIS variable name that receives the enumerator value"
    )
    index: int = Field(
        default=0,
        description="Column index in the enumerator result set (0-based)"
    )
```

#### ForEachLoopDetails

```python
class ForEachLoopDetails(BaseModel):
    enumerator_type: str = Field(
        default="unknown",
        description="Enumerator type: ForEachItem, ForEachFile, "
                    "ForEachADO, ForEachADOEnum, ForEachFromVar, "
                    "ForEachNodeList, ForEachSMOEnum"
    )
    variable_mappings: list[ForEachVariableMapping] = Field(
        default_factory=list,
        description="Mappings from enumerator columns to SSIS variables"
    )
```

#### ParameterBinding

```python
class ParameterBinding(BaseModel):
    parameter_name: str = Field(
        description="Parameter name or marker (e.g., 0, Param1)"
    )
    variable_name: str = Field(
        description="SSIS variable name bound to this parameter"
    )
    direction: str = Field(
        default="Input",
        description="Binding direction: Input, Output, InputOutput, ReturnValue"
    )
```

#### ResultBinding

```python
class ResultBinding(BaseModel):
    result_name: str = Field(
        description="Result set column name or ordinal"
    )
    variable_name: str = Field(
        description="SSIS variable name that receives the result"
    )
```

#### TaskBindings

```python
class TaskBindings(BaseModel):
    parameter_bindings: list[ParameterBinding] = Field(
        default_factory=list,
        description="Input/output parameter bindings for Execute SQL Tasks"
    )
    result_bindings: list[ResultBinding] = Field(
        default_factory=list,
        description="Result set bindings for Execute SQL Tasks"
    )
```

#### EventHandler

```python
class EventHandler(BaseModel):
    event_name: str = Field(
        description="Event that triggers this handler (e.g., OnError, OnWarning)"
    )
    target_task_name: str = Field(
        default="",
        description="Task name this handler is attached to (empty = package-level)"
    )
    tasks: list["Task"] = Field(
        default_factory=list,
        description="Tasks executed when the event fires"
    )
    precedence_constraints: list["PrecedenceConstraint"] = Field(
        default_factory=list,
        description="Precedence constraints between handler tasks"
    )
```

#### PackageConfig

```python
class PackageConfig(BaseModel):
    config_type: str = Field(
        description="Configuration type: XMLFile, EnvironmentVariable, "
                    "ParentPackageVariable, SQLServer, RegistryEntry"
    )
    target_property: str = Field(
        description="DTS property path being configured"
    )
    config_string: str = Field(
        default="",
        description="Configuration connection string or path"
    )
```

### 3.2 Enhanced Task Model

The existing `Task` model gains optional fields for the new detail types. All new fields default to `None` or empty lists, preserving backward compatibility:

```python
class Task(BaseModel):
    name: str
    task_type: str
    description: str = ""
    sql: str | None = None
    connection_name: str | None = None
    is_disabled: bool = False
    expression: str | None = None

    # -- New fields (all optional, backward compatible) --
    script_info: ScriptTaskInfo | None = None
    for_loop_details: ForLoopDetails | None = None
    foreach_loop_details: ForEachLoopDetails | None = None
    bindings: TaskBindings | None = None
```

### 3.3 Enhanced SSISPackage Model

```python
class SSISPackage(BaseModel):
    name: str
    description: str = ""
    creation_date: str = ""
    creator_name: str = ""
    tasks: list[Task] = []
    connections: list[Connection] = []
    variables: list[Variable] = []
    precedence_constraints: list[PrecedenceConstraint] = []
    configurations: list[PackageConfig] = []

    # -- New fields (all optional, backward compatible) --
    event_handlers: list[EventHandler] = Field(
        default_factory=list,
        description="Package-level and task-level event handlers"
    )
    package_configs: list[PackageConfig] = Field(
        default_factory=list,
        description="SSIS package configurations (XML, SQL, EnvVar, etc.)"
    )
    version_build: int = Field(
        default=0,
        description="Package version build number from DTS:VersionBuild"
    )
```

### 3.4 Backward Compatibility

Every new field has a default value:

| Model | Field | Default |
|---|---|---|
| `Task` | `script_info` | `None` |
| `Task` | `for_loop_details` | `None` |
| `Task` | `foreach_loop_details` | `None` |
| `Task` | `bindings` | `None` |
| `SSISPackage` | `event_handlers` | `[]` |
| `SSISPackage` | `package_configs` | `[]` |
| `SSISPackage` | `version_build` | `0` |

Existing serialized `SSISPackage` JSON (without these fields) deserializes without error via `SSISPackage.model_validate(json_data)`.

---

## 4. Parser Enhancements

All new parser methods are added to the `SSISParser` class in `parsers/ssis_parser.py`. Each method enriches the `Task` or `SSISPackage` being built. They are called from the existing `_parse_task()` method based on the task's `@TaskType` attribute.

### 4.1 _parse_script_task

Extracts the full source code, language, entry method, and variable access lists from a Script Task's embedded `<ScriptTaskProject>` element.

```python
def _parse_script_task(self, task_elem: ET.Element) -> ScriptTaskInfo | None:
    """Extract Script Task source code and metadata from the embedded project."""
    script_project = task_elem.find(
        ".//dft:ScriptTaskProject",
        self._ns
    )
    if script_project is None:
        return None

    language_attr = script_project.get("ScriptLanguage", "")
    if "VisualBasic" in language_attr or "VB" in language_attr:
        language = "VB"
    elif "CSharp" in language_attr:
        language = "CSharp"
    else:
        language = "unknown"

    entry_method = script_project.get("EntryPoint", "ScriptMain")

    script_block = script_project.find("dft:ScriptBlock", self._ns)
    code = ""
    if script_block is not None:
        code = script_block.text or ""

    read_only_vars: list[str] = []
    read_write_vars: list[str] = []

    ro_elem = task_elem.find(
        ".//dft:ScriptTask/dft:ReadOnlyVariables",
        self._ns
    )
    if ro_elem is not None and ro_elem.text:
        read_only_vars = [v.strip() for v in ro_elem.text.split(",") if v.strip()]

    rw_elem = task_elem.find(
        ".//dft:ScriptTask/dft:ReadWriteVariables",
        self._ns
    )
    if rw_elem is not None and rw_elem.text:
        read_write_vars = [v.strip() for v in rw_elem.text.split(",") if v.strip()]

    return ScriptTaskInfo(
        language=language,
        entry_method=entry_method,
        code=code,
        read_only_vars=read_only_vars,
        read_write_vars=read_write_vars,
    )
```

### 4.2 _parse_for_loop_details

Extracts the three expressions that define a For Loop container.

```python
def _parse_for_loop_details(self, task_elem: ET.Element) -> ForLoopDetails | None:
    """Extract InitExpression, EvalExpression, AssignExpression from a For Loop."""
    for_loop = task_elem.find(".//dft:ForLoop", self._ns)
    if for_loop is None:
        return None

    return ForLoopDetails(
        init_expression=for_loop.get("InitExpression", ""),
        eval_expression=for_loop.get("EvalExpression", ""),
        assign_expression=for_loop.get("AssignExpression", ""),
    )
```

### 4.3 _parse_foreach_loop_details

Extracts the enumerator type and variable mappings from a ForEach Loop container.

```python
FOREACH_ENUM_TYPES: dict[str, str] = {
    "{A6F1D358-1CF3-4227-9C18-9E7B9D2A4067}": "ForEachItem",
    "{3A4A0E5F-624C-4E0F-8B7A-9F3E2D1C0B4A}": "ForEachFile",
    "{4F0B0D0E-9C2A-4D3B-8E1F-7A6B5C4D3E2F}": "ForEachADO",
    "{50D7A5F4-8F2C-4A1B-9D3E-6C5B4A3F2E1D}": "ForEachADOEnum",
    "{6C5B4A3F-2E1D-4F0B-9C2A-8E1F7A6B5C4D}": "ForEachFromVar",
    "{8E1F7A6B-5C4D-4F0B-9C2A-3A4A0E5F624C}": "ForEachNodeList",
    "{9C2A8E1F-7A6B-4D3B-8E1F-4F0B0D0E9C2A}": "ForEachSMOEnum",
}


def _parse_foreach_loop_details(self, task_elem: ET.Element) -> ForEachLoopDetails | None:
    """Extract enumerator type and variable mappings from a ForEach Loop."""
    foreach_loop = task_elem.find(".//dft:ForEachLoop", self._ns)
    if foreach_loop is None:
        return None

    enumerator_elem = foreach_loop.find(
        ".//dft:ForEachEnumerator", self._ns
    )
    enumerator_type = "unknown"
    if enumerator_elem is not None:
        guid = enumerator_elem.get(
            "ForEachEnumeratorType", ""
        )
        enumerator_type = FOREACH_ENUM_TYPES.get(guid, "unknown")

    mappings: list[ForEachVariableMapping] = []
    for vm_elem in foreach_loop.findall(
        ".//dft:ForEachVariableMapping", self._ns
    ):
        variable = vm_elem.get("VariableName", "")
        index = int(vm_elem.get("ValueIndex", "0"))
        mappings.append(
            ForEachVariableMapping(variable=variable, index=index)
        )

    return ForEachLoopDetails(
        enumerator_type=enumerator_type,
        variable_mappings=mappings,
    )
```

### 4.4 _parse_sql_task_bindings

Extracts parameter bindings and result bindings from an Execute SQL Task.

```python
def _parse_sql_task_bindings(self, task_elem: ET.Element) -> TaskBindings | None:
    """Extract parameter and result bindings from an Execute SQL Task."""
    param_bindings: list[ParameterBinding] = []
    result_bindings: list[ResultBinding] = []

    for pb_elem in task_elem.findall(
        ".//dft:ExecuteSQLTask/dft:ParameterBindings/dft:ParameterBinding",
        self._ns,
    ):
        param_bindings.append(ParameterBinding(
            parameter_name=pb_elem.get("ParameterName", ""),
            variable_name=pb_elem.get("DtsVariableName", ""),
            direction=pb_elem.get("ParameterDirection", "Input"),
        ))

    for rb_elem in task_elem.findall(
        ".//dft:ExecuteSQLTask/dft:ResultBindings/dft:ResultBinding",
        self._ns,
    ):
        result_bindings.append(ResultBinding(
            result_name=rb_elem.get("ResultName", ""),
            variable_name=rb_elem.get("DtsVariableName", ""),
        ))

    if not param_bindings and not result_bindings:
        return None

    return TaskBindings(
        parameter_bindings=param_bindings,
        result_bindings=result_bindings,
    )
```

### 4.5 _decode_sql

Decodes XML entities in SQL statements so that the persisted model contains clean, executable SQL.

```python
import html


def _decode_sql(self, sql: str) -> str:
    """Decode XML entities in a SQL string.

    Handles standard XML entities (&lt;, &gt;, &amp;, &quot;, &apos;)
    as well as numeric character references.
    """
    if not sql:
        return sql
    return html.unescape(sql)
```

### 4.6 _parse_event_handlers

Extracts package-level and task-level event handlers from the `<EventHandlers>` element.

```python
def _parse_event_handlers(self, pkg_elem: ET.Element) -> list[EventHandler]:
    """Extract all event handlers from the package XML."""
    handlers: list[EventHandler] = []
    eh_container = pkg_elem.find("dft:EventHandlers", self._ns)
    if eh_container is None:
        return handlers

    for eh_elem in eh_container.findall("dft:EventHandler", self._ns):
        handler = self._parse_single_event_handler(eh_elem)
        if handler is not None:
            handlers.append(handler)

    return handlers


def _parse_single_event_handler(self, eh_elem: ET.Element) -> EventHandler | None:
    """Parse a single <EventHandler> element."""
    event_name = eh_elem.get("EventID", "")
    target_task_name = eh_elem.get("TaskName", "")

    tasks: list[Task] = []
    for exec_elem in eh_elem.findall("dft:Executables/dft:Executable", self._ns):
        task = self._parse_task(exec_elem)
        if task is not None:
            tasks.append(task)

    constraints: list[PrecedenceConstraint] = []
    for pc_elem in eh_elem.findall(
        "dft:PrecedenceConstraints/dft:PrecedenceConstraint", self._ns
    ):
        constraints.append(PrecedenceConstraint(
            from_task=pc_elem.get("From", ""),
            to_task=pc_elem.get("To", ""),
            value=pc_elem.get("Value", ""),
        ))

    return EventHandler(
        event_name=event_name,
        target_task_name=target_task_name,
        tasks=tasks,
        precedence_constraints=constraints,
    )
```

### 4.7 _parse_package_configs

Extracts SSIS package configurations (XML file, environment variable, SQL Server, etc.).

```python
def _parse_package_configs(self, pkg_elem: ET.Element) -> list[PackageConfig]:
    """Extract package configurations from <PackageConfigurations>."""
    configs: list[PackageConfig] = []
    pc_container = pkg_elem.find(
        "dft:PackageConfigurations", self._ns
    )
    if pc_container is None:
        return configs

    for pc_elem in pc_container.findall(
        "dft:PackageConfiguration", self._ns
    ):
        config_type_attr = pc_elem.get("ConfigurationType", "0")
        type_map = {
            "0": "XMLFile",
            "1": "EnvironmentVariable",
            "2": "ParentPackageVariable",
            "3": "SQLServer",
            "4": "RegistryEntry",
        }
        config_type = type_map.get(config_type_attr, "Unknown")
        target_property = pc_elem.get("TargetProperty", "")
        config_string = pc_elem.get("ConfigurationString", "")

        configs.append(PackageConfig(
            config_type=config_type,
            target_property=target_property,
            config_string=config_string,
        ))

    return configs
```

### 4.8 version_build Extraction

The `version_build` is extracted from the package-level `DTS:VersionBuild` attribute during the initial `parse()` call:

```python
def _extract_version_build(self, pkg_elem: ET.Element) -> int:
    """Extract DTS:VersionBuild from the package element."""
    vb = pkg_elem.get("{www.microsoft.com/SqlServer/Dts}VersionBuild", "0")
    try:
        return int(vb)
    except (ValueError, TypeError):
        return 0
```

### 4.9 Integration into _parse_task

The existing `_parse_task()` method is extended to call the new enrichment methods based on the task type. The SQL field is decoded using `_decode_sql()`:

```python
def _parse_task(self, exec_elem: ET.Element) -> Task | None:
    """Parse an <Executable> element into a Task, enriching with type-specific details."""
    name = exec_elem.get("Name", "")
    task_type = exec_elem.get("ExecutableType", "")
    description = exec_elem.get("Description", "")

    sql = self._extract_sql(exec_elem)
    if sql:
        sql = self._decode_sql(sql)

    connection_name = self._extract_connection(exec_elem)
    is_disabled = exec_elem.get("Disabled", "0") == "1"
    expression = self._extract_expression(exec_elem)

    task = Task(
        name=name,
        task_type=task_type,
        description=description,
        sql=sql,
        connection_name=connection_name,
        is_disabled=is_disabled,
        expression=expression,
    )

    # -- Type-specific enrichment --
    if "ScriptTask" in task_type:
        task.script_info = self._parse_script_task(exec_elem)

    if "ForLoop" in task_type:
        task.for_loop_details = self._parse_for_loop_details(exec_elem)

    if "ForEachLoop" in task_type:
        task.foreach_loop_details = self._parse_foreach_loop_details(exec_elem)

    if "ExecuteSQLTask" in task_type:
        task.bindings = self._parse_sql_task_bindings(exec_elem)

    return task
```

---

## 5. Extractor to Formatter Refactor

### 5.1 Current Flow

```
.dtsx file
  |
  +--> SSISExtractor.extract()
         |
         +--> Direct XML parsing (720 lines)
         +--> Markdown rendering
         +--> Return markdown string
```

The `SSISExtractor` does both parsing and formatting in a single monolithic method. It opens the `.dtsx` file, walks the XML tree, and builds markdown strings inline.

### 5.2 New Flow

```
.dtsx file
  |
  +--> SSISExtractor.extract()
         |
         +--> SSISParser.parse()         --> SSISPackage (Pydantic model)
         +--> Persist SSISPackage        --> DB (ssis_package_json column)
         +--> SSISFormatter.format()     --> Markdown string (tiered)
         +--> Return markdown string
```

The `SSISExtractor` becomes a thin orchestrator. All XML parsing moves to `SSISParser`. All markdown rendering moves to `SSISFormatter`.

### 5.3 SSISFormatter Class

New file: `extractors/ssis_formatter.py`

```python
from enum import Enum

from models.ssis_package import SSISPackage


class FormatTier(Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class SSISFormatter:
    """Format an SSISPackage model into markdown at the requested detail tier."""

    def __init__(self, package: SSISPackage, tier: FormatTier = FormatTier.L2):
        self.package = package
        self.tier = tier

    def format(self, focus_task_name: str | None = None) -> str:
        """Produce a markdown summary of the package at the configured tier."""
        sections: list[str] = []
        sections.append(self._format_package_summary())
        sections.append(self._format_connections())
        sections.append(self._format_variables())
        sections.append(self._format_tasks(focus_task_name))
        sections.append(self._format_precedence_constraints())
        if self.tier == FormatTier.L3:
            sections.append(self._format_event_handlers())
            sections.append(self._format_package_configs())
        return "\n".join(s for s in sections if s)

    def _format_package_summary(self) -> str:
        """Format the package header with name, description, versionBuild."""
        lines = [f"## Package: {self.package.name}"]
        if self.package.description:
            lines.append(f"**Description:** {self.package.description}")
        if self.package.creator_name:
            lines.append(f"**Creator:** {self.package.creator_name}")
        if self.package.creation_date:
            lines.append(f"**Created:** {self.package.creation_date}")
        if self.tier == FormatTier.L1:
            lines.append(f"**Task Count:** {len(self.package.tasks)}")
            lines.append(f"**Connection Count:** {len(self.package.connections)}")
            lines.append(f"**Variable Count:** {len(self.package.variables)}")
        return "\n".join(lines)

    def _format_connections(self) -> str:
        """Format connection managers."""
        if not self.package.connections:
            return ""
        lines = ["### Connections"]
        for conn in self.package.connections:
            lines.append(f"- **{conn.name}** ({conn.connection_type})")
        return "\n".join(lines)

    def _format_variables(self) -> str:
        """Format package variables."""
        if not self.package.variables:
            return ""
        lines = ["### Variables"]
        for var in self.package.variables:
            lines.append(f"- **{var.name}** ({var.data_type})")
        return "\n".join(lines)

    def _format_tasks(self, focus_task_name: str | None = None) -> str:
        """Format tasks, with detail level controlled by tier."""
        if not self.package.tasks:
            return ""
        lines = ["### Tasks"]
        for task in self.package.tasks:
            is_focused = (
                focus_task_name is not None
                and task.name == focus_task_name
            )
            lines.append(self._format_single_task(task, is_focused))
        return "\n".join(lines)

    def _format_single_task(self, task: Task, is_focused: bool = False) -> str:
        """Format a single task with tier-appropriate detail."""
        parts = [f"- **{task.name}** ({task.task_type})"]
        if task.is_disabled:
            parts.append("(DISABLED)")
        if task.connection_name:
            parts.append(f"Connection: {task.connection_name}")

        if task.sql:
            if self.tier == FormatTier.L1:
                pass
            elif self.tier == FormatTier.L2:
                truncated = task.sql[:200] + ("..." if len(task.sql) > 200 else "")
                parts.append(f"SQL: {truncated}")
            elif self.tier == FormatTier.L3:
                parts.append(f"SQL:\n``sql\n{task.sql}\n``")

        if task.script_info:
            if self.tier == FormatTier.L1:
                parts.append(f"Script: {task.script_info.language}")
            elif self.tier == FormatTier.L2:
                parts.append(
                    f"Script: {task.script_info.language} "
                    f"sig={task.script_info.code_signature}"
                )
            elif self.tier == FormatTier.L3 and is_focused:
                parts.append(
                    f"Script ({task.script_info.language}):\n"
                    f"``\n{task.script_info.code}\n``"
                )
            elif self.tier == FormatTier.L3:
                parts.append(
                    f"Script: {task.script_info.language} "
                    f"({task.script_info.code_char_count} chars)"
                )

        if task.for_loop_details:
            if self.tier in (FormatTier.L2, FormatTier.L3):
                d = task.for_loop_details
                parts.append(
                    f"ForLoop: init={d.init_expression} "
                    f"eval={d.eval_expression} assign={d.assign_expression}"
                )

        if task.foreach_loop_details:
            if self.tier in (FormatTier.L2, FormatTier.L3):
                d = task.foreach_loop_details
                parts.append(f"ForEach: type={d.enumerator_type}")
                if self.tier == FormatTier.L3:
                    for m in d.variable_mappings:
                        parts.append(f"  map: {m.variable} <- index {m.index}")

        if task.bindings:
            if self.tier in (FormatTier.L2, FormatTier.L3):
                for pb in task.bindings.parameter_bindings:
                    parts.append(
                        f"Param: {pb.parameter_name} <- {pb.variable_name} ({pb.direction})"
                    )
                for rb in task.bindings.result_bindings:
                    parts.append(
                        f"Result: {rb.result_name} -> {rb.variable_name}"
                    )

        return " ".join(parts)

    def _format_precedence_constraints(self) -> str:
        """Format precedence constraints between tasks."""
        if not self.package.precedence_constraints:
            return ""
        lines = ["### Precedence Constraints"]
        for pc in self.package.precedence_constraints:
            lines.append(f"- {pc.from_task} -> {pc.to_task} ({pc.value})")
        return "\n".join(lines)

    def _format_event_handlers(self) -> str:
        """Format event handlers (L3 only)."""
        if not self.package.event_handlers:
            return ""
        lines = ["### Event Handlers"]
        for eh in self.package.event_handlers:
            target = eh.target_task_name or "Package"
            lines.append(f"- **{eh.event_name}** on {target}")
            for t in eh.tasks:
                lines.append(f"  - {t.name} ({t.task_type})")
        return "\n".join(lines)

    def _format_package_configs(self) -> str:
        """Format package configurations (L3 only)."""
        if not self.package.package_configs:
            return ""
        lines = ["### Package Configurations"]
        for cfg in self.package.package_configs:
            lines.append(f"- **{cfg.config_type}**: {cfg.target_property}")
        return "\n".join(lines)
```

### 5.4 SSISExtractor.extract() Refactor

The `SSISExtractor.extract()` method is simplified to orchestrate parse -> persist -> format:

```python
class SSISExtractor(BaseExtractor):
    """Extract SSIS package information using Parser + Formatter."""

    def extract(self, file_path: str) -> str:
        """Parse the .dtsx file, persist the model, and return formatted markdown."""
        parser = SSISParser()
        package = parser.parse(file_path)

        self._persist_package(package)

        formatter = SSISFormatter(package, tier=FormatTier.L2)
        return formatter.format()
```

### 5.5 Extractor Registry Unchanged

The extractor registry entry for `.dtsx` files remains unchanged. The `SSISExtractor` class name and its `extract()` signature are preserved. Downstream code that calls `extractor.extract(path)` continues to work without modification.

---

## 6. SSISPackage Persistence

### 6.1 ORM Column Addition

A new JSONB column `ssis_package_json` is added to the `ETLPackage` SQLAlchemy ORM model:

```python
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB


class ETLPackage(Base):
    __tablename__ = "etl_packages"

    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    source_file_path = Column(Text)
    # ... existing columns ...

    ssis_package_json = Column(
        JSONB,
        nullable=True,
        doc="Full SSISPackage model serialized as JSON. "
            "Populated during parse. Used by Formatter and Generator.",
    )
```

### 6.2 Alembic Migration

```python
"""Add ssis_package_json column to etl_packages

Revision ID: a1b2c3d4e5f6
Revises: previous_revision
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


def upgrade() -> None:
    op.add_column(
        "etl_packages",
        sa.Column(
            "ssis_package_json",
            JSONB,
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("etl_packages", "ssis_package_json")
```

### 6.3 Persistence Logic

After parsing, the `SSISPackage` model is serialized and stored:

```python
import json

from models.ssis_package import SSISPackage


def persist_ssis_package(
    session: Session,
    etl_package_id: int,
    package: SSISPackage,
) -> None:
    """Serialize and persist an SSISPackage to the database.

    Uses model_dump() with mode='json' to ensure all fields
    (including computed fields) are JSON-serializable.
    """
    json_data = package.model_dump(mode="json")
    stmt = (
        update(ETLPackage)
        .where(ETLPackage.id == etl_package_id)
        .values(ssis_package_json=json_data)
    )
    session.execute(stmt)
    session.commit()
```

### 6.4 Deserialization

Components that need the `SSISPackage` model deserialize from the persisted JSON:

```python
def load_ssis_package(session: Session, etl_package_id: int) -> SSISPackage | None:
    """Load and deserialize an SSISPackage from the database.

    Returns None if the package has not been persisted yet
    (backward compatibility during migration).
    """
    result = session.execute(
        select(ETLPackage.ssis_package_json).where(
            ETLPackage.id == etl_package_id
        )
    ).scalar_one_or_none()

    if result is None:
        return None

    return SSISPackage.model_validate(result)
```

### 6.5 Generator Change

The `SSISGenerator` is updated to read from the persisted `SSISPackage` instead of re-parsing the `.dtsx` file. A fallback to the old behavior ensures compatibility during migration:

```python
class SSISGenerator:
    """Generate Python conversion artifacts from an SSISPackage model."""

    def generate(self, etl_package_id: int, file_path: str) -> list[Artifact]:
        """Generate artifacts, preferring the persisted SSISPackage."""
        package = load_ssis_package(self.session, etl_package_id)

        if package is None:
            # Fallback: re-parse from disk (backward compat during migration)
            parser = SSISParser()
            package = parser.parse(file_path)

        return self._generate_from_package(package)

    def _generate_from_package(self, package: SSISPackage) -> list[Artifact]:
        """Generate Python artifacts from an SSISPackage model."""
        artifacts: list[Artifact] = []
        for task in package.tasks:
            artifact = self._generate_task(task, package)
            if artifact is not None:
                artifacts.append(artifact)
        return artifacts
```

---

## 7. Tiered Formatting L1/L2/L3

### 7.1 FormatTier Enum

```python
from enum import Enum


class FormatTier(Enum):
    L1 = "L1"  # Structure only
    L2 = "L2"  # Structure + signatures
    L3 = "L3"  # Full detail (focused)
```

### 7.2 Tiered _format_package_summary

The package summary is rendered differently at each tier:

```python
def _format_package_summary(self) -> str:
    """Format the package header with tier-appropriate detail."""
    lines = [f"## Package: {self.package.name}"]

    if self.package.description:
        lines.append(f"**Description:** {self.package.description}")

    if self.tier == FormatTier.L1:
        lines.append(f"**Task Count:** {len(self.package.tasks)}")
        lines.append(f"**Connection Count:** {len(self.package.connections)}")
        lines.append(f"**Variable Count:** {len(self.package.variables)}")
        conn_names = [c.name for c in self.package.connections]
        if conn_names:
            lines.append(f"**Connections:** {', '.join(conn_names)}")
        return "\n".join(lines)

    if self.tier in (FormatTier.L2, FormatTier.L3):
        if self.package.creator_name:
            lines.append(f"**Creator:** {self.package.creator_name}")
        if self.package.creation_date:
            lines.append(f"**Created:** {self.package.creation_date}")
        if self.package.version_build:
            lines.append(f"**Version Build:** {self.package.version_build}")

        task_types = {}
        for t in self.package.tasks:
            task_types[t.task_type] = task_types.get(t.task_type, 0) + 1
        type_summary = ", ".join(
            f"{k}:{v}" for k, v in sorted(task_types.items())
        )
        lines.append(f"**Task Types:** {type_summary}")

    return "\n".join(lines)
```

### 7.3 L1: Structure Only

L1 formatting produces a minimal summary suitable for strategy classification and package listing. It contains:

- Package name and description
- Task count, connection count, variable count
- Connection names (comma-separated)
- No SQL, no script code, no loop expressions, no bindings

**Typical output:**

```
## Package: LoadCustomerData
**Description:** Loads customer data from staging to warehouse
**Task Count:** 12
**Connection Count:** 3
**Variable Count:** 8
**Connections:** StagingDB, WarehouseDB, FTPServer
```

### 7.4 L2: Structure + Signatures

L2 formatting adds truncated signatures to the L1 structure. It contains:

- Everything in L1
- Creator, creation date, version build, task type summary
- SQL truncated to 200 characters
- Script Task language + code signature (first meaningful line)
- For Loop expressions
- ForEach Loop enumerator type
- Binding summaries (parameter name + variable name, no full detail)

**Typical output:**

```
## Package: LoadCustomerData
**Description:** Loads customer data from staging to warehouse
**Creator:** ETLAdmin
**Created:** 2024-03-15T10:30:00
**Version Build:** 42
**Task Types:** ExecuteSQLTask:5, DataFlowTask:4, ScriptTask:2, ForEachLoop:1

### Tasks
- **Extract Customers** (ExecuteSQLTask) Connection: StagingDB
  SQL: SELECT CustomerID, Name, Email FROM dbo.StagingCustomers WHERE...
  Param: 0 <- User::BatchID (Input)
  Result: CustomerID -> User::MaxCustomerID
- **Transform Data** (ScriptTask)
  Script: VB sig=Dts.Variables("InputData").Value
- **Loop Over Files** (ForEachLoop)
  ForEach: type=ForEachFile
- **Process Batch** (ForLoop)
  ForLoop: init=@i=0 eval=@i<@BatchCount assign=@i=@i+1
```

### 7.5 L3: Full Detail

L3 formatting produces complete detail for a focused task, with summary for all other tasks. It contains:

- Everything in L2
- Full SQL (not truncated) for the focused task
- Full Script Task source code for the focused task
- Full variable mappings for ForEach Loops
- Full parameter and result bindings
- Column mappings from Data Flow components
- Event handlers
- Package configurations

L3 requires a `focus_task_name` parameter. The focused task receives full detail; all other tasks receive L2-level detail.

**Typical output (focused on "Transform Data"):**

```
## Package: LoadCustomerData
**Description:** Loads customer data from staging to warehouse
**Creator:** ETLAdmin
**Created:** 2024-03-15T10:30:00
**Version Build:** 42
**Task Types:** ExecuteSQLTask:5, DataFlowTask:4, ScriptTask:2, ForEachLoop:1

### Tasks
- **Extract Customers** (ExecuteSQLTask) Connection: StagingDB
  SQL: SELECT CustomerID, Name, Email FROM dbo.StagingCustomers...
  Param: 0 <- User::BatchID (Input)
- **Transform Data** (ScriptTask) Connection: StagingDB
  Script (VB):
  ``
  Public Sub ScriptMain()
      Dim inputData As String = Dts.Variables("InputData").Value.ToString()
      Dim transformed As String = TransformCustomer(inputData)
      Dts.Variables("OutputData").Value = transformed
      Dts.TaskResult = ScriptResults.Success
  End Sub
  ``
- **Loop Over Files** (ForEachLoop)
  ForEach: type=ForEachFile
    map: User::FileName <- index 0
    map: User::FilePath <- index 1

### Event Handlers
- **OnError** on Transform Data
  - LogError (ExecuteSQLTask)

### Package Configurations
- **XMLFile**: \Package.Variables[User::ConnectionString].Properties[Value]
```

### 7.6 Consumer Usage Table

| Consumer | Default Tier | focus_task_name | Notes |
|---|---|---|---|
| StrategyClassifier | L1 | None | Only needs structure for heuristic scoring |
| Code Generation (unfocused) | L2 | None | Needs signatures to plan generation |
| Code Generation (focused) | L3 | Task name | Full detail for the task being generated |
| Package Listing UI | L1 | None | Minimal info for browse/search |
| Package Detail UI | L2 | None | Signatures for task overview |
| Audit/Debug | L3 | None | Full detail for all tasks |

### 7.7 Token Budget Estimation

| Tier | Small Package (<20 tasks) | Medium (20-100 tasks) | Large (100+ tasks) |
|---|---|---|---|
| L1 | ~150 tokens | ~300 tokens | ~500 tokens |
| L2 | ~500 tokens | ~1,500 tokens | ~3,000 tokens |
| L3 (focused) | ~1,500 tokens | ~4,000 tokens | ~8,000 tokens |
| L3 (unfocused) | ~2,000 tokens | ~8,000 tokens | ~20,000+ tokens |

### 7.8 Optional Prompt-Size Guard

An optional guard prevents L3 formatting from exceeding a token budget:

```python
def format(self, focus_task_name: str | None = None, max_tokens: int | None = None) -> str:
    """Produce a markdown summary with optional token budget enforcement.

    If max_tokens is set and the L3 output exceeds it, the formatter
    falls back to L2 for non-focused tasks and truncates SQL to 500 chars.
    """
    result = self._build_markdown(focus_task_name)

    if max_tokens is not None:
        estimated_tokens = len(result) // 4
        if estimated_tokens > max_tokens:
            result = self._build_markdown_truncated(focus_task_name, max_tokens)

    return result


def _build_markdown_truncated(self, focus_task_name: str | None, max_tokens: int) -> str:
    """Build markdown with aggressive truncation to fit within token budget."""
    char_budget = max_tokens * 4
    sections: list[str] = []
    sections.append(self._format_package_summary())
    sections.append(self._format_connections())
    sections.append(self._format_variables())

    task_section = self._format_tasks(focus_task_name, sql_truncate=500)
    sections.append(task_section)

    combined = "\n".join(s for s in sections if s)
    if len(combined) > char_budget:
        combined = combined[:char_budget - 3] + "..."
    return combined
```

---

## 8. Generator Enhancements

### 8.1 Script Task: Comment-Block Original Code

When generating Python from a Script Task, the Generator now includes the original source code as a comment block, followed by a placeholder for the Lakebridge Switch conversion:

```python
def _generate_script_task(self, task: Task) -> str:
    """Generate Python for a Script Task, preserving original code as comments."""
    lines: list[str] = []

    if task.script_info is None:
        return "# Script Task: original code not available\npass\n"

    info = task.script_info
    lines.append(f"# Script Task: {task.name}")
    lines.append(f"# Original Language: {info.language}")
    lines.append(f"# Entry Method: {info.entry_method}")

    if info.read_only_vars:
        lines.append(f"# Read-Only Variables: {', '.join(info.read_only_vars)}")
    if info.read_write_vars:
        lines.append(f"# Read-Write Variables: {', '.join(info.read_write_vars)}")

    lines.append("#")
    lines.append("# Original code:")
    for code_line in info.code.splitlines():
        lines.append(f"#   {code_line}")

    lines.append("#")
    lines.append("# TODO: Convert using Lakebridge Switch or manual review")
    lines.append(f"def {info.entry_method.lower()}():")
    lines.append("    raise NotImplementedError(")
    lines.append(f'        "Script Task \'{task.name}\' requires manual conversion"')
    lines.append("    )")

    return "\n".join(lines)
```

### 8.2 Script Task: Lakebridge Switch Integration

For Script Tasks where Lakebridge Switch is available, the Generator can invoke it to produce a Python translation:

```python
def _generate_script_task_with_lakebridge(
    self, task: Task, lakebridge_path: str | None = None
) -> str:
    """Generate Python for a Script Task using Lakebridge Switch if available.

    Falls back to comment-block preservation if Lakebridge is not configured
    or fails.
    """
    if lakebridge_path is None or task.script_info is None:
        return self._generate_script_task(task)

    try:
        translated = self._invoke_lakebridge(
            code=task.script_info.code,
            language=task.script_info.language,
            lakebridge_path=lakebridge_path,
        )
        return translated
    except Exception:
        return self._generate_script_task(task)


def _invoke_lakebridge(
    self, code: str, language: str, lakebridge_path: str
) -> str:
    """Invoke Lakebridge Switch CLI to translate VB/C# to Python.

    Raises RuntimeError if the translation fails.
    """
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(
        suffix=".vb" if language == "VB" else ".cs",
        mode="w",
        delete=False,
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [lakebridge_path, "translate", tmp_path, "--target", "python"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Lakebridge failed: {result.stderr}")
        return result.stdout
    finally:
        import os
        os.unlink(tmp_path)
```

### 8.3 ForEach Loop: Proper Python For-Loop Patterns

The Generator now produces idiomatic Python for-loop patterns using the ForEachLoopDetails:

```python
def _generate_foreach_loop(self, task: Task, inner_code: str) -> str:
    """Generate a Python for-loop from ForEachLoopDetails."""
    if task.foreach_loop_details is None:
        return f"# ForEach Loop: {task.name}\n{inner_code}\n"

    details = task.foreach_loop_details
    lines: list[str] = []

    if details.enumerator_type == "ForEachFile":
        file_var = "file_path"
        if details.variable_mappings:
            file_var = details.variable_mappings[0].variable
        lines.append(f"import glob")
        lines.append(f"for {file_var} in glob.glob(file_pattern):")
        lines.append(f"    # {task.name}")
        for line in inner_code.splitlines():
            lines.append(f"    {line}")

    elif details.enumerator_type == "ForEachItem":
        item_var = "item"
        if details.variable_mappings:
            item_var = details.variable_mappings[0].variable
        lines.append(f"for {item_var} in items:")
        lines.append(f"    # {task.name}")
        for line in inner_code.splitlines():
            lines.append(f"    {line}")

    elif details.enumerator_type == "ForEachADO":
        record_var = "record"
        if details.variable_mappings:
            record_var = details.variable_mappings[0].variable
        lines.append(f"for {record_var} in recordset:")
        lines.append(f"    # {task.name}")
        for line in inner_code.splitlines():
            lines.append(f"    {line}")

    else:
        lines.append(f"# ForEach Loop ({details.enumerator_type}): {task.name}")
        lines.append(f"for item in items:")
        for line in inner_code.splitlines():
            lines.append(f"    {line}")

    return "\n".join(lines)
```

### 8.4 Binding-Aware SQL: Parameterized Queries

When generating Python for an Execute SQL Task that has parameter bindings, the Generator produces parameterized queries:

```python
def _generate_execute_sql_task(self, task: Task) -> str:
    """Generate Python for an Execute SQL Task with parameter bindings."""
    lines: list[str] = []
    lines.append(f"# Execute SQL Task: {task.name}")

    if task.sql is None:
        lines.append("pass")
        return "\n".join(lines)

    sql = task.sql
    if task.bindings and task.bindings.parameter_bindings:
        lines.append("params = {")
        for pb in task.bindings.parameter_bindings:
            var_name = pb.variable_name.replace("User::", "").replace("System::", "")
            lines.append(f'    "{pb.parameter_name}": {var_name.lower()},')
        lines.append("}")
        lines.append(f"cursor.execute(\"\"\"{sql}\"\"\", params)")
    else:
        lines.append(f"cursor.execute(\"\"\"{sql}\"\"\")")

    if task.bindings and task.bindings.result_bindings:
        lines.append("result = cursor.fetchall()")
        for rb in task.bindings.result_bindings:
            var_name = rb.variable_name.replace("User::", "").replace("System::", "")
            lines.append(f"{var_name.lower()} = result[0][\"{rb.result_name}\"]")

    return "\n".join(lines)
```

---

## 9. Impact on StrategyClassifier

### 9.1 Enhanced Indicators

The `StrategyClassifier` currently uses basic indicators from the `SSISPackage` model (task types, connection types, variable count). The enriched model provides new indicators:

```python
from dataclasses import dataclass


@dataclass
class EnhancedIndicators:
    """Extended indicators for strategy classification."""

    # Existing indicators
    task_count: int
    task_types: dict[str, int]
    connection_types: dict[str, int]
    variable_count: int
    has_expressions: bool

    # New indicators from enriched model
    script_task_count: int = 0
    script_languages: list[str] = None
    script_total_code_chars: int = 0
    foreach_enumerator_types: list[str] = None
    has_parameterized_sql: bool = False
    has_event_handlers: bool = False
    has_package_configs: bool = False
    for_loop_count: int = 0
    foreach_loop_count: int = 0

    def __post_init__(self):
        if self.script_languages is None:
            self.script_languages = []
        if self.foreach_enumerator_types is None:
            self.foreach_enumerator_types = []
```

### 9.2 Indicator Extraction

```python
def extract_enhanced_indicators(package: SSISPackage) -> EnhancedIndicators:
    """Extract enhanced indicators from an enriched SSISPackage model."""
    task_types: dict[str, int] = {}
    script_task_count = 0
    script_languages: list[str] = []
    script_total_code_chars = 0
    foreach_enumerator_types: list[str] = []
    has_parameterized_sql = False
    for_loop_count = 0
    foreach_loop_count = 0

    for task in package.tasks:
        task_types[task.task_type] = task_types.get(task.task_type, 0) + 1

        if task.script_info is not None:
            script_task_count += 1
            if task.script_info.language not in script_languages:
                script_languages.append(task.script_info.language)
            script_total_code_chars += task.script_info.code_char_count

        if task.for_loop_details is not None:
            for_loop_count += 1

        if task.foreach_loop_details is not None:
            foreach_loop_count += 1
            enum_type = task.foreach_loop_details.enumerator_type
            if enum_type not in foreach_enumerator_types:
                foreach_enumerator_types.append(enum_type)

        if task.bindings is not None and task.bindings.parameter_bindings:
            has_parameterized_sql = True

    connection_types: dict[str, int] = {}
    for conn in package.connections:
        ct = conn.connection_type
        connection_types[ct] = connection_types.get(ct, 0) + 1

    has_expressions = any(t.expression for t in package.tasks)

    return EnhancedIndicators(
        task_count=len(package.tasks),
        task_types=task_types,
        connection_types=connection_types,
        variable_count=len(package.variables),
        has_expressions=has_expressions,
        script_task_count=script_task_count,
        script_languages=script_languages,
        script_total_code_chars=script_total_code_chars,
        foreach_enumerator_types=foreach_enumerator_types,
        has_parameterized_sql=has_parameterized_sql,
        has_event_handlers=len(package.event_handlers) > 0,
        has_package_configs=len(package.package_configs) > 0,
        for_loop_count=for_loop_count,
        foreach_loop_count=foreach_loop_count,
    )
```

### 9.3 Strategy Decision Refinements

New indicators refine strategy decisions:

| Indicator | Impact on Strategy |
|---|---|
| `script_task_count > 0` | Increases "complex_script" strategy weight. Script Tasks require manual or Lakebridge conversion. |
| `script_total_code_chars > 5000` | Strong signal for "complex_script" over "simple_etl". Large scripts dominate migration effort. |
| `"CSharp" in script_languages` | May prefer Lakebridge Switch over manual VB conversion. |
| `"ForEachFile" in foreach_enumerator_types` | Indicates file-based iteration; suggests file I/O patterns in generated code. |
| `"ForEachADO" in foreach_enumerator_types` | Indicates recordset iteration; suggests cursor-based patterns. |
| `has_parameterized_sql` | Indicates mature SQL practices; generated code should use parameterized queries. |
| `has_event_handlers` | Increases "complex_control_flow" weight. Event handlers add control flow complexity. |
| `has_package_configs` | Indicates environment-specific configuration; generated code needs config management. |
| `for_loop_count > 2` | Increases "complex_control_flow" weight. Multiple loops suggest iterative processing. |

```python
def refine_strategy(
    base_strategy: str, indicators: EnhancedIndicators
) -> str:
    """Refine the base strategy using enhanced indicators."""
    if indicators.script_task_count > 0 and indicators.script_total_code_chars > 5000:
        return "complex_script"

    if indicators.has_event_handlers and indicators.for_loop_count > 2:
        return "complex_control_flow"

    if indicators.has_parameterized_sql and indicators.script_task_count == 0:
        return "parameterized_etl"

    return base_strategy
```

---

## 10. Frontend Changes

### 10.1 Dropzone Accepted Types

The file upload dropzone is updated to accept `.dtsx` files as a first-class input type:

``	ypescript
const ACCEPTED_FILE_TYPES = {
  ".dtsx": "application/xml",
  ".sql": "text/plain",
  ".py": "text/x-python",
  ".json": "application/json",
  ".zip": "application/zip",
};
```

When a `.dtsx` file is uploaded:

1. The file is sent to the backend parse endpoint
2. The backend runs `SSISParser.parse()` and persists the `SSISPackage`
3. The backend returns the L1-formatted summary for the upload confirmation UI
4. The artifact group defaults to `code_to_migrate` (see below)

### 10.2 Default Artifact Group

SSIS packages are automatically assigned to the `code_to_migrate` artifact group, since their primary purpose is migration to Python:

``	ypescript
function getArtifactGroup(fileName: string): string {
  if (fileName.endsWith(".dtsx")) {
    return "code_to_migrate";
  }
  if (fileName.endsWith(".sql")) {
    return "code_to_migrate";
  }
  if (fileName.endsWith(".py")) {
    return "generated_code";
  }
  return "other";
}
```

### 10.3 Script Task Code Preview

The package detail view includes a collapsible Script Task code preview with syntax highlighting:

``	ypescript
interface ScriptTaskPreviewProps {
  taskName: string;
  language: string;
  code: string;
  charCount: number;
}

function ScriptTaskPreview({ taskName, language, code, charCount }: ScriptTaskPreviewProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="script-task-preview">
      <div className="script-task-header" onClick={() => setExpanded(!expanded)}>
        <span className="task-name">{taskName}</span>
        <span className="language-badge">{language}</span>
        <span className="char-count">{charCount} chars</span>
        <span className="expand-icon">{expanded ? "v" : ">"}</span>
      </div>
      {expanded && (
        <div className="script-task-code">
          <SyntaxHighlighter language={language === "VB" ? "vbnet" : "csharp"}>
            {code}
          </SyntaxHighlighter>
        </div>
      )}
    </div>
  );
}
```

The syntax highlighter uses `react-syntax-highlighter` with the `vbnet` grammar for VB Script Tasks and `csharp` for C# Script Tasks.

### 10.4 Package Summary View

The package summary view uses the L2-formatted markdown for the overview, with a task list that allows clicking a task to see its L3 detail:

``	ypescript
function PackageSummaryView({ packageId }: { packageId: number }) {
  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const { data: l2Summary } = usePackageSummary(packageId, "L2");
  const { data: l3Detail } = useTaskDetail(packageId, selectedTask, "L3");

  return (
    <div className="package-summary">
      <MarkdownRenderer content={l2Summary} />
      {selectedTask && (
        <TaskDetailPanel
          taskName={selectedTask}
          detail={l3Detail}
          onClose={() => setSelectedTask(null)}
        />
      )}
    </div>
  );
}
```

---

## 11. Testing Strategy

### 11.1 Parser Tests

#### Script Task Parsing

```python
import pytest
from parsers.ssis_parser import SSISParser
from models.ssis_package import ScriptTaskInfo


class TestParseScriptTask:
    def test_vb_script_task(self, tmp_path):
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(DTSX_WITH_VB_SCRIPT)
        parser = SSISParser()
        package = parser.parse(str(dtsx))
        script_task = next(t for t in package.tasks if "Script" in t.task_type)
        assert script_task.script_info is not None
        assert script_task.script_info.language == "VB"
        assert "ScriptMain" in script_task.script_info.code

    def test_csharp_script_task(self, tmp_path):
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(DTSX_WITH_CSHARP_SCRIPT)
        parser = SSISParser()
        package = parser.parse(str(dtsx))
        script_task = next(t for t in package.tasks if "Script" in t.task_type)
        assert script_task.script_info.language == "CSharp"

    def test_script_task_with_variables(self, tmp_path):
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(DTSX_WITH_SCRIPT_VARS)
        parser = SSISParser()
        package = parser.parse(str(dtsx))
        task = next(t for t in package.tasks if t.script_info is not None)
        assert "User::BatchID" in task.script_info.read_only_vars
        assert "User::OutputData" in task.script_info.read_write_vars

    def test_no_script_task(self, tmp_path):
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(DTSX_NO_SCRIPT)
        parser = SSISParser()
        package = parser.parse(str(dtsx))
        assert all(t.script_info is None for t in package.tasks)
```

#### For Loop Parsing

```python
class TestParseForLoop:
    def test_for_loop_expressions(self, tmp_path):
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(DTSX_WITH_FOR_LOOP)
        parser = SSISParser()
        package = parser.parse(str(dtsx))
        loop = next(t for t in package.tasks if t.for_loop_details is not None)
        assert loop.for_loop_details.init_expression == "@Counter = 0"
        assert loop.for_loop_details.eval_expression == "@Counter < 10"
        assert loop.for_loop_details.assign_expression == "@Counter = @Counter + 1"

    def test_no_for_loop(self, tmp_path):
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(DTSX_NO_LOOPS)
        parser = SSISParser()
        package = parser.parse(str(dtsx))
        assert all(t.for_loop_details is None for t in package.tasks)
```

#### ForEach Loop Parsing

```python
class TestParseForEachLoop:
    def test_foreach_file_loop(self, tmp_path):
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(DTSX_WITH_FOREACH_FILE)
        parser = SSISParser()
        package = parser.parse(str(dtsx))
        loop = next(t for t in package.tasks if t.foreach_loop_details is not None)
        assert loop.foreach_loop_details.enumerator_type == "ForEachFile"
        assert len(loop.foreach_loop_details.variable_mappings) == 2

    def test_foreach_ado_loop(self, tmp_path):
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(DTSX_WITH_FOREACH_ADO)
        parser = SSISParser()
        package = parser.parse(str(dtsx))
        loop = next(t for t in package.tasks if t.foreach_loop_details is not None)
        assert loop.foreach_loop_details.enumerator_type == "ForEachADO"
```

#### Bindings Parsing

```python
class TestParseBindings:
    def test_parameter_bindings(self, tmp_path):
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(DTSX_WITH_PARAM_BINDINGS)
        parser = SSISParser()
        package = parser.parse(str(dtsx))
        sql_task = next(t for t in package.tasks if t.bindings is not None)
        assert len(sql_task.bindings.parameter_bindings) == 2
        assert sql_task.bindings.parameter_bindings[0].variable_name == "User::BatchID"

    def test_result_bindings(self, tmp_path):
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(DTSX_WITH_RESULT_BINDINGS)
        parser = SSISParser()
        package = parser.parse(str(dtsx))
        sql_task = next(t for t in package.tasks if t.bindings is not None)
        assert len(sql_task.bindings.result_bindings) == 1
        assert sql_task.bindings.result_bindings[0].result_name == "MaxID"
```

#### XML Decoding

```python
class TestDecodeSQL:
    def test_xml_entities_decoded(self, tmp_path):
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(DTSX_WITH_XML_ENTITIES_IN_SQL)
        parser = SSISParser()
        package = parser.parse(str(dtsx))
        sql_task = next(t for t in package.tasks if t.sql)
        assert "<" in sql_task.sql
        assert ">" in sql_task.sql
        assert "&lt;" not in sql_task.sql
        assert "&gt;" not in sql_task.sql

    def test_amp_entity_decoded(self, tmp_path):
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(DTSX_WITH_AMP_ENTITY)
        parser = SSISParser()
        package = parser.parse(str(dtsx))
        sql_task = next(t for t in package.tasks if t.sql)
        assert "&" in sql_task.sql
        assert "&amp;" not in sql_task.sql
```

#### Event Handlers

```python
class TestParseEventHandlers:
    def test_package_level_handler(self, tmp_path):
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(DTSX_WITH_ONERROR_HANDLER)
        parser = SSISParser()
        package = parser.parse(str(dtsx))
        assert len(package.event_handlers) == 1
        assert package.event_handlers[0].event_name == "OnError"
        assert package.event_handlers[0].target_task_name == ""

    def test_task_level_handler(self, tmp_path):
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(DTSX_WITH_TASK_HANDLER)
        parser = SSISParser()
        package = parser.parse(str(dtsx))
        assert len(package.event_handlers) == 1
        assert package.event_handlers[0].target_task_name == "Extract Data"
```

#### Package Configs

```python
class TestParsePackageConfigs:
    def test_xml_file_config(self, tmp_path):
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(DTSX_WITH_XML_CONFIG)
        parser = SSISParser()
        package = parser.parse(str(dtsx))
        assert len(package.package_configs) == 1
        assert package.package_configs[0].config_type == "XMLFile"
```

### 11.2 Formatter Tests

```python
class TestSSISFormatter:
    def test_l1_output_structure_only(self):
        package = SSISPackage(name="Test", tasks=[...])
        formatter = SSISFormatter(package, tier=FormatTier.L1)
        output = formatter.format()
        assert "Task Count:" in output
        assert "SQL:" not in output

    def test_l2_output_has_signatures(self):
        package = SSISPackage(name="Test", tasks=[...])
        formatter = SSISFormatter(package, tier=FormatTier.L2)
        output = formatter.format()
        assert "SQL:" in output
        assert "sig=" in output

    def test_l3_output_has_full_code(self):
        package = SSISPackage(name="Test", tasks=[...])
        formatter = SSISFormatter(package, tier=FormatTier.L3)
        output = formatter.format(focus_task_name="Script1")
        assert "ScriptMain" in output

    def test_formatter_matches_old_extractor_output(self):
        """Regression: Formatter L2 output matches old Extractor output."""
        package = SSISParser().parse(SAMPLE_DTSX_PATH)
        formatter = SSISFormatter(package, tier=FormatTier.L2)
        new_output = formatter.format()

        old_extractor = SSISExtractor()
        old_output = old_extractor.extract(SAMPLE_DTSX_PATH)

        assert normalize(new_output) == normalize(old_output)
```

### 11.3 Persistence Tests

```python
class TestPersistence:
    def test_round_trip(self, db_session):
        package = SSISPackage(
            name="Test",
            tasks=[Task(name="T1", task_type="ExecuteSQLTask", sql="SELECT 1")],
        )
        persist_ssis_package(db_session, etl_package_id=1, package=package)
        loaded = load_ssis_package(db_session, etl_package_id=1)
        assert loaded is not None
        assert loaded.name == "Test"
        assert len(loaded.tasks) == 1
        assert loaded.tasks[0].sql == "SELECT 1"

    def test_backward_compat_missing_column(self, db_session):
        """Existing rows without ssis_package_json return None."""
        loaded = load_ssis_package(db_session, etl_package_id=999)
        assert loaded is None

    def test_backward_compat_old_json(self, db_session):
        """JSON without new fields deserializes with defaults."""
        old_json = {"name": "Old", "tasks": [], "connections": [], "variables": []}
        package = SSISPackage.model_validate(old_json)
        assert package.event_handlers == []
        assert package.version_build == 0
```

### 11.4 Tiered Formatting Tests

```python
class TestTieredFormatting:
    def test_l1_size_bound(self):
        package = make_large_package(task_count=200)
        formatter = SSISFormatter(package, tier=FormatTier.L1)
        output = formatter.format()
        assert len(output) < 2000  # chars, ~500 tokens

    def test_l2_size_bound(self):
        package = make_medium_package(task_count=50)
        formatter = SSISFormatter(package, tier=FormatTier.L2)
        output = formatter.format()
        assert len(output) < 10000  # chars, ~2500 tokens

    def test_l3_focused_size_bound(self):
        package = make_large_package(task_count=200)
        formatter = SSISFormatter(package, tier=FormatTier.L3)
        output = formatter.format(focus_task_name="Task_42")
        assert len(output) < 40000  # chars, ~10000 tokens

    def test_l3_prompt_guard(self):
        package = make_large_package(task_count=200)
        formatter = SSISFormatter(package, tier=FormatTier.L3)
        output = formatter.format(focus_task_name="Task_42", max_tokens=4000)
        estimated_tokens = len(output) // 4
        assert estimated_tokens <= 4000
```

### 11.5 Generator Tests

```python
class TestGeneratorScriptTask:
    def test_script_code_preserved_as_comments(self):
        task = Task(
            name="MyScript",
            task_type="ScriptTask",
            script_info=ScriptTaskInfo(
                language="VB",
                entry_method="ScriptMain",
                code="Dts.Variables(\"X\").Value = 1",
                read_only_vars=[],
                read_write_vars=["User::X"],
            ),
        )
        gen = SSISGenerator()
        output = gen._generate_script_task(task)
        assert "# Original code:" in output
        assert "Dts.Variables" in output
        assert "NotImplementedError" in output

    def test_foreach_file_generates_glob(self):
        task = Task(
            name="LoopFiles",
            task_type="ForEachLoop",
            foreach_loop_details=ForEachLoopDetails(
                enumerator_type="ForEachFile",
                variable_mappings=[
                    ForEachVariableMapping(variable="User::FilePath", index=0),
                ],
            ),
        )
        gen = SSISGenerator()
        output = gen._generate_foreach_loop(task, "process(file_path)")
        assert "glob.glob" in output

    def test_binding_aware_sql(self):
        task = Task(
            name="GetData",
            task_type="ExecuteSQLTask",
            sql="SELECT * FROM T WHERE ID = ?",
            bindings=TaskBindings(
                parameter_bindings=[
                    ParameterBinding(
                        parameter_name="0",
                        variable_name="User::TargetID",
                        direction="Input",
                    )
                ],
                result_bindings=[],
            ),
        )
        gen = SSISGenerator()
        output = gen._generate_execute_sql_task(task)
        assert "params = {" in output
        assert "targetid" in output.lower()
```

### 11.6 Integration Tests

```python
class TestIntegration:
    def test_end_to_end_parse_format_generate(self, tmp_path):
        """Full pipeline: parse -> persist -> format -> generate."""
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(REALISTIC_DTSX)

        parser = SSISParser()
        package = parser.parse(str(dtsx))

        formatter_l1 = SSISFormatter(package, tier=FormatTier.L1)
        l1_output = formatter_l1.format()
        assert "Task Count:" in l1_output

        formatter_l2 = SSISFormatter(package, tier=FormatTier.L2)
        l2_output = formatter_l2.format()
        assert len(l2_output) > len(l1_output)

        formatter_l3 = SSISFormatter(package, tier=FormatTier.L3)
        l3_output = formatter_l3.format(focus_task_name=package.tasks[0].name)
        assert len(l3_output) > len(l2_output)

        gen = SSISGenerator()
        artifacts = gen._generate_from_package(package)
        assert len(artifacts) > 0

    def test_no_reparse_in_generator(self, tmp_path, db_session):
        """Generator uses persisted model, not re-parsing from disk."""
        dtsx = tmp_path / "test.dtsx"
        dtsx.write_text(REALISTIC_DTSX)

        parser = SSISParser()
        package = parser.parse(str(dtsx))
        persist_ssis_package(db_session, etl_package_id=1, package=package)

        gen = SSISGenerator(session=db_session)
        with patch.object(SSISParser, "parse") as mock_parse:
            artifacts = gen.generate(etl_package_id=1, file_path=str(dtsx))
            mock_parse.assert_not_called()
```

---

## 12. Migration Path

The migration is executed in 10 incremental steps. Each step is independently deployable and backward compatible.

### Step 1: Add New Schema Fields (Backward Compatible)

**Files changed:** `models/ssis_package.py`

**Action:** Add `ScriptTaskInfo`, `ForLoopDetails`, `ForEachVariableMapping`, `ForEachLoopDetails`, `ParameterBinding`, `ResultBinding`, `TaskBindings`, `EventHandler`, `PackageConfig` models. Add new optional fields to `Task` and `SSISPackage` with defaults.

**Risk:** None. All new fields have defaults. Existing code that constructs `Task` or `SSISPackage` without the new fields continues to work.

**Validation:** Run existing test suite. All tests must pass without modification.

### Step 2: Add Parser Methods

**Files changed:** `parsers/ssis_parser.py`

**Action:** Add `_parse_script_task()`, `_parse_for_loop_details()`, `_parse_foreach_loop_details()`, `_parse_sql_task_bindings()`, `_decode_sql()`, `_parse_event_handlers()`, `_parse_single_event_handler()`, `_parse_package_configs()`, `_extract_version_build()`. Integrate into `_parse_task()`.

**Risk:** Low. New methods are additive. The existing `_parse_task()` return type and behavior for non-enriched task types is unchanged.

**Validation:** Add parser tests (Section 11.1). Run against sample `.dtsx` files.

### Step 3: Add SSISFormatter

**Files changed:** `extractors/ssis_formatter.py` (new)

**Action:** Create `SSISFormatter` class with `FormatTier` enum and `format()` method. Implement `_format_package_summary()`, `_format_connections()`, `_format_variables()`, `_format_tasks()`, `_format_single_task()`, `_format_precedence_constraints()`, `_format_event_handlers()`, `_format_package_configs()`.

**Risk:** None. New file, no existing code affected.

**Validation:** Add formatter tests (Section 11.2). Verify L2 output matches old Extractor output on sample files.

### Step 4: Refactor SSISExtractor

**Files changed:** `extractors/ssis_extractor.py`

**Action:** Replace XML-parsing logic in `extract()` with `SSISParser.parse()` + `SSISFormatter.format()`. Remove direct XML manipulation code. Preserve the `extract()` signature and return type.

**Risk:** Medium. This is the most impactful step. The Extractor's output must match the previous output exactly (verified by regression tests).

**Validation:** Run formatter regression test (`test_formatter_matches_old_extractor_output`). Manual review of LLM prompt outputs on 5+ sample packages.

**Rollback:** Revert to old `SSISExtractor` code if regression test fails.

### Step 5: Add ssis_package_json Column

**Files changed:** `models/etl_package.py`, `alembic/versions/xxxx_add_ssis_package_json.py`

**Action:** Add `ssis_package_json` JSONB column to `ETLPackage`. Create Alembic migration.

**Risk:** Low. Nullable column, no data loss.

**Validation:** Run migration on staging database. Verify existing rows are unaffected.

### Step 6: Update Parse Job to Persist

**Files changed:** `jobs/parse_job.py` (or equivalent)

**Action:** After `SSISParser.parse()`, call `persist_ssis_package()` to store the model in `ssis_package_json`.

**Risk:** Low. Additive operation. Existing rows without the column continue to function.

**Validation:** Run parse job on sample packages. Verify `ssis_package_json` is populated. Run round-trip test.

### Step 7: Update Generator Caller

**Files changed:** `generators/ssis_generator.py`, `services/generation_service.py` (or equivalent)

**Action:** Update `SSISGenerator.generate()` to call `load_ssis_package()` first, falling back to `SSISParser.parse()` if the persisted model is not available.

**Risk:** Low. Fallback ensures backward compatibility during migration.

**Validation:** Run generator on packages with and without persisted models. Verify output is identical.

### Step 8: Add Tiered Formatting

**Files changed:** `extractors/ssis_formatter.py`, `services/strategy_service.py`, `services/generation_service.py`

**Action:** Wire `FormatTier.L1` to StrategyClassifier, `FormatTier.L2` to unfocused generation, `FormatTier.L3` to focused generation. Add `focus_task_name` and `max_tokens` parameters to generation endpoints.

**Risk:** Low. Tier selection is a parameter; default is L2 (matches old behavior).

**Validation:** Run tiered formatting tests (Section 11.4). Verify L1/L2/L3 size bounds.

### Step 9: Update Templates

**Files changed:** LLM prompt templates

**Action:** Update prompt templates to use tiered formatting. Strategy classification prompts use L1. Code generation prompts use L2 for planning and L3 for focused generation.

**Risk:** Low. Template changes are additive. Old templates continue to work.

**Validation:** Run A/B comparison of LLM outputs with old vs new templates on sample packages.

### Step 10: Frontend Changes

**Files changed:** Frontend components (dropzone, package detail, script preview)

**Action:** Add `.dtsx` to accepted types, default artifact group to `code_to_migrate`, add Script Task code preview with syntax highlighting.

**Risk:** Low. UI-only changes.

**Validation:** Manual UI testing. Verify `.dtsx` upload, artifact grouping, and script preview.

---

## 13. Risk Assessment

### 13.1 Backward Compatibility Risk: LOW

**Threat:** New schema fields break existing code that constructs `Task` or `SSISPackage`.

**Mitigation:** All new fields have default values (`None`, `[]`, `0`). Pydantic's default behavior allows construction without specifying optional fields. Existing serialized JSON deserializes without error.

**Verification:** Run existing test suite without modification. All tests must pass.

### 13.2 Performance Risk: LOW

**Threat:** Single parse pass is slower than the current approach.

**Analysis:** The current approach performs **three** parse passes (Extractor + Parser + Generator). The new approach performs **one** parse pass plus one format pass (which reads from the in-memory model, not the file). Even if the enriched parse is 20% slower than the old Parser, the total pipeline time decreases because we eliminate two redundant passes.

| Operation | Current | New | Delta |
|---|---|---|---|
| Extractor (XML parse + format) | ~2s | -- | -2s |
| Parser (XML parse) | ~1.5s | ~1.8s | +0.3s |
| Generator (XML re-parse) | ~1.5s | -- | -1.5s |
| Formatter (model -> markdown) | -- | ~0.1s | +0.1s |
| **Total** | **~5s** | **~1.9s** | **-3.1s** |

**Verification:** Benchmark parse + format on 10 sample packages of varying size.

### 13.3 Data Loss Risk: NONE

**Threat:** The refactor loses information that the old Extractor captured.

**Mitigation:** The `SSISFormatter` at L2 tier reproduces the same markdown output as the old `SSISExtractor`. This is verified by the regression test `test_formatter_matches_old_extractor_output`. The new model captures **more** information (script code, loop details, bindings), not less.

**Verification:** Regression test on 5+ sample packages. Manual review of output.

### 13.4 Migration Risk: LOW

**Threat:** The Alembic migration fails or corrupts existing data.

**Mitigation:** The migration adds a single nullable JSONB column. No existing data is modified. The `downgrade()` drops the column. Existing rows with `ssis_package_json = NULL` are handled by the `load_ssis_package()` fallback.

**Verification:** Run migration on staging database. Verify existing rows are unaffected. Run downgrade and verify column is removed.

### 13.5 LLM Context Risk: MITIGATED

**Threat:** Large packages produce L3 output that exceeds LLM context windows.

**Mitigation:** Tiered formatting (L1/L2/L3) ensures that each consumer receives appropriately sized output. The `max_tokens` guard truncates output if it exceeds the budget. The default tier for code generation is L2 (not L3), which is bounded at ~2,000 tokens for medium packages.

**Verification:** Tiered formatting size bound tests (Section 11.4). Prompt-size guard test.

### 13.6 Regression Risk: MEDIUM

**Threat:** The Formatter output differs from the old Extractor output, causing LLM prompt drift.

**Mitigation:** Step 4 (Refactor SSISExtractor) includes a mandatory regression test that compares Formatter L2 output with old Extractor output. Any differences must be reviewed and approved before deployment.

**Verification:** Regression test on 5+ sample packages. A/B comparison of LLM outputs.

### 13.7 Risk Summary Table

| Risk | Severity | Mitigation | Residual |
|---|---|---|---|
| Backward compat | Low | Default values on all new fields | Minimal |
| Performance | Low | Single parse vs triple parse | Positive (faster) |
| Data loss | None | Formatter reproduces Extractor output | None |
| Migration | Low | Nullable column, fallback path | Minimal |
| LLM context | Medium | Tiered formatting, max_tokens guard | Low |
| Regression | Medium | Mandatory regression test, A/B review | Low |

---

## 14. Summary of Changes

### 14.1 Files Changed

| File | Change Type | Lines Added | Lines Removed | Description |
|---|---|---|---|---|
| `models/ssis_package.py` | Modified | +120 | -0 | New Pydantic models + enhanced Task/SSISPackage |
| `parsers/ssis_parser.py` | Modified | +180 | -5 | New parser methods + integration in _parse_task |
| `extractors/ssis_formatter.py` | **New** | +200 | -0 | SSISFormatter class with tiered formatting |
| `extractors/ssis_extractor.py` | Modified | +15 | -650 | Refactored to use Parser + Formatter |
| `models/etl_package.py` | Modified | +5 | -0 | ssis_package_json column |
| `alembic/versions/xxxx.py` | **New** | +20 | -0 | Migration for ssis_package_json |
| `jobs/parse_job.py` | Modified | +10 | -0 | Persist SSISPackage after parse |
| `generators/ssis_generator.py` | Modified | +80 | -30 | Read from persisted model, enhanced generation |
| `services/strategy_service.py` | Modified | +30 | -5 | Enhanced indicators + strategy refinement |
| `services/generation_service.py` | Modified | +15 | -5 | Tiered formatting integration |
| `tests/test_parser_enrichment.py` | **New** | +200 | -0 | Parser enrichment tests |
| `tests/test_ssis_formatter.py` | **New** | +150 | -0 | Formatter + tiered formatting tests |
| `tests/test_persistence.py` | **New** | +80 | -0 | Persistence round-trip tests |
| `tests/test_generator_enriched.py` | **New** | +100 | -0 | Generator tests with enriched model |

### 14.2 New Files

1. `extractors/ssis_formatter.py` -- SSISFormatter class (200 lines)
2. `alembic/versions/xxxx_add_ssis_package_json.py` -- Migration (20 lines)
3. `tests/test_parser_enrichment.py` -- Parser tests (200 lines)
4. `tests/test_ssis_formatter.py` -- Formatter tests (150 lines)
5. `tests/test_persistence.py` -- Persistence tests (80 lines)
6. `tests/test_generator_enriched.py` -- Generator tests (100 lines)

### 14.3 Deleted Methods

The following methods are removed from `SSISExtractor` as their logic moves to `SSISParser` or `SSISFormatter`:

| Method | Destination |
|---|---|
| `SSISExtractor._extract_script_code()` | `SSISParser._parse_script_task()` |
| `SSISExtractor._extract_for_loop()` | `SSISParser._parse_for_loop_details()` |
| `SSISExtractor._extract_foreach_loop()` | `SSISParser._parse_foreach_loop_details()` |
| `SSISExtractor._extract_bindings()` | `SSISParser._parse_sql_task_bindings()` |
| `SSISExtractor._render_task_markdown()` | `SSISFormatter._format_single_task()` |
| `SSISExtractor._render_connections()` | `SSISFormatter._format_connections()` |
| `SSISExtractor._render_variables()` | `SSISFormatter._format_variables()` |
| `SSISExtractor._render_precedence()` | `SSISFormatter._format_precedence_constraints()` |

### 14.4 New Methods

| Method | Location | Lines |
|---|---|---|
| `SSISParser._parse_script_task()` | `parsers/ssis_parser.py` | 35 |
| `SSISParser._parse_for_loop_details()` | `parsers/ssis_parser.py` | 10 |
| `SSISParser._parse_foreach_loop_details()` | `parsers/ssis_parser.py` | 25 |
| `SSISParser._parse_sql_task_bindings()` | `parsers/ssis_parser.py` | 25 |
| `SSISParser._decode_sql()` | `parsers/ssis_parser.py` | 8 |
| `SSISParser._parse_event_handlers()` | `parsers/ssis_parser.py` | 15 |
| `SSISParser._parse_single_event_handler()` | `parsers/ssis_parser.py` | 25 |
| `SSISParser._parse_package_configs()` | `parsers/ssis_parser.py` | 20 |
| `SSISParser._extract_version_build()` | `parsers/ssis_parser.py` | 8 |
| `SSISFormatter.format()` | `extractors/ssis_formatter.py` | 15 |
| `SSISFormatter._format_package_summary()` | `extractors/ssis_formatter.py` | 25 |
| `SSISFormatter._format_connections()` | `extractors/ssis_formatter.py` | 10 |
| `SSISFormatter._format_variables()` | `extractors/ssis_formatter.py` | 10 |
| `SSISFormatter._format_tasks()` | `extractors/ssis_formatter.py` | 15 |
| `SSISFormatter._format_single_task()` | `extractors/ssis_formatter.py` | 60 |
| `SSISFormatter._format_precedence_constraints()` | `extractors/ssis_formatter.py` | 10 |
| `SSISFormatter._format_event_handlers()` | `extractors/ssis_formatter.py` | 12 |
| `SSISFormatter._format_package_configs()` | `extractors/ssis_formatter.py` | 10 |
| `SSISFormatter._build_markdown_truncated()` | `extractors/ssis_formatter.py` | 15 |
| `persist_ssis_package()` | `services/persistence.py` | 15 |
| `load_ssis_package()` | `services/persistence.py` | 15 |
| `extract_enhanced_indicators()` | `services/strategy_service.py` | 40 |
| `refine_strategy()` | `services/strategy_service.py` | 12 |
| `SSISGenerator._generate_script_task()` | `generators/ssis_generator.py` | 25 |
| `SSISGenerator._generate_script_task_with_lakebridge()` | `generators/ssis_generator.py` | 20 |
| `SSISGenerator._generate_foreach_loop()` | `generators/ssis_generator.py` | 35 |
| `SSISGenerator._generate_execute_sql_task()` | `generators/ssis_generator.py` | 25 |

### 14.5 Net Line Count

| Category | Lines Added | Lines Removed | Net |
|---|---|---|---|
| Models | +120 | -0 | +120 |
| Parser | +180 | -5 | +175 |
| Formatter (new) | +200 | -0 | +200 |
| Extractor | +15 | -650 | -635 |
| ORM + Migration | +25 | -0 | +25 |
| Generator | +80 | -30 | +50 |
| Strategy | +30 | -5 | +25 |
| Services | +25 | -5 | +20 |
| Tests (new) | +530 | -0 | +530 |
| **Total** | **+1,205** | **-695** | **+510** |

### 14.6 Architecture Diagram (Before vs After)

**Before:**

```
.dtsx --> SSISExtractor --> markdown --> LLM
     |
     +--> SSISParser --> SSISPackage (partial) --> DB
     |
     +--> SSISGenerator --> artifacts (re-parses .dtsx from disk)
```

**After:**

```
.dtsx --> SSISParser --> SSISPackage (complete) --> DB (ssis_package_json)
                                                     |
                                                     +--> SSISFormatter --> markdown --> LLM
                                                     |
                                                     +--> SSISGenerator --> artifacts
                                                     |
                                                     +--> StrategyClassifier --> strategy
```

The single `SSISPackage` model is the authoritative source of truth. All consumers read from it. No component re-parses the `.dtsx` file.

---

*End of specification.*

