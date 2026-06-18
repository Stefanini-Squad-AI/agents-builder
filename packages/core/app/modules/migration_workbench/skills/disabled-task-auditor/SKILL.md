# Disabled Task Auditor

Audit disabled tasks in SSIS packages to determine migration decisions: exclude, include with warning, or require manual review.

## When to Use

- Identifying disabled tasks that might be accidentally excluded from migration
- Understanding why tasks were disabled (temporary debugging vs. permanent deprecation)
- Making informed decisions about disabled code during migration
- Documenting disabled task inventory for audit trails

## Capabilities

1. **Detect Disabled Tasks** - Find all tasks with `Disabled="true"` attribute
2. **Analyze Context** - Examine surrounding annotations and comments
3. **Assess Risk** - Determine if disabled task contains critical logic
4. **Recommend Action** - Suggest exclude, include, or review

## Disabled Task Categories

### 1. Safe to Exclude
Characteristics:
- Contains test/debug keywords in name
- References non-production tables (test_, tmp_, debug_)
- Commented with "deprecated" or "replaced by"
- No business logic, only logging/tracing

```xml
<!-- Example: Safe to exclude -->
<DTS:Executable DTS:Disabled="true">
  <DTS:Property DTS:Name="ObjectName">DEBUG_Log_Counts</DTS:Property>
</DTS:Executable>
```

### 2. Include with Warning
Characteristics:
- Contains potentially active business logic
- Recently disabled (check package modified date)
- References production tables
- No clear deprecation annotation

```xml
<!-- Example: Include with warning -->
<DTS:Executable DTS:Disabled="true">
  <DTS:Property DTS:Name="ObjectName">Load_Legacy_Customers</DTS:Property>
  <!-- SQL references production tables -->
</DTS:Executable>
```

### 3. Requires Manual Review
Characteristics:
- Critical business rule logic
- No annotation explaining why disabled
- Dependencies on active tasks
- Part of complex workflow branching

## Usage Instructions

### 1. Audit Single Package

```
Audit disabled tasks in package [package_name] and recommend migration actions.
```

### 2. Audit Entire Project

```
Generate a disabled task report for all packages in project [project_name].
```

### 3. Risk Assessment

```
Assess risk level for disabled tasks containing business logic in [package_name].
```

## Output Format

```yaml
package: CustomerDataPipeline
total_tasks: 45
disabled_tasks: 8
disabled_percentage: 17.8%

audit_results:
  - task_name: "DEBUG_Trace_Execution"
    task_type: "Script Task"
    recommendation: EXCLUDE
    confidence: 0.95
    reason: "Debug/trace task with no business logic"
    evidence:
      - "Name contains 'DEBUG'"
      - "No SQL statements"
      - "Only writes to log table"
    
  - task_name: "Load_Historical_Orders_Pre2020"
    task_type: "Execute SQL Task"
    recommendation: REVIEW
    confidence: 0.60
    reason: "Contains business logic, unclear why disabled"
    evidence:
      - "References production table: orders"
      - "Contains MERGE statement"
      - "No deprecation annotation found"
    affected_tables:
      - orders
      - order_history
    sql_preview: "MERGE INTO orders_archive..."

summary:
  exclude: 4
  include_with_warning: 1
  requires_review: 3
```

## Decision Matrix

| Indicator | Weight | EXCLUDE | WARNING | REVIEW |
|-----------|--------|---------|---------|--------|
| Name contains DEBUG/TEST | +0.3 | ✓ | | |
| References tmp_/test_ tables | +0.2 | ✓ | | |
| Has deprecation comment | +0.3 | ✓ | | |
| Contains MERGE/INSERT | -0.4 | | ✓ | |
| References production tables | -0.3 | | ✓ | |
| No annotation at all | -0.3 | | | ✓ |
| Has dependencies | -0.4 | | | ✓ |
| Recently modified (<6mo) | -0.2 | | ✓ | |

**Score Interpretation:**
- Score > 0.7: EXCLUDE
- Score 0.4 - 0.7: WARNING
- Score < 0.4: REVIEW

## Detection Queries

### Find Disabled Tasks
```python
# In SSIS XML
disabled_tasks = package.xpath(
    "//DTS:Executable[@DTS:Disabled='true']",
    namespaces=NAMESPACES
)
```

### Check for Deprecation Annotations
```python
keywords = ['deprecated', 'obsolete', 'replaced', 'no longer used', 'legacy']
for annotation in package.annotations:
    if any(kw in annotation.text.lower() for kw in keywords):
        task.marked_deprecated = True
```

## Integration

This skill integrates with:

- **SSIS Parser** - Extracts disabled attribute and task metadata
- **Dependency Analyzer** - Checks if disabled tasks have dependencies
- **Documentation Generator** - Includes disabled task audit in reports

## Best Practices

1. **Document Decisions** - Record why each disabled task was excluded or included
2. **Verify with SMEs** - Disabled tasks with business logic need stakeholder review
3. **Check Recently Disabled** - Tasks disabled close to migration may be temporary
4. **Preserve for Reference** - Even excluded tasks should be documented
5. **Test After Migration** - Verify no critical logic was lost from disabled tasks
