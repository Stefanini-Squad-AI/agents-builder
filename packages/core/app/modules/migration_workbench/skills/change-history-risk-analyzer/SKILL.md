# Change History Risk Analyzer

Analyze package modification history to assess migration risk based on change frequency, recent modifications, and complexity growth.

## When to Use

- Prioritizing packages for migration based on stability
- Identifying high-risk packages that need extra attention
- Understanding package evolution and complexity trends
- Planning testing effort based on change patterns

## Capabilities

1. **Change Frequency Analysis** - Track how often packages are modified
2. **Recency Assessment** - Identify recently changed packages requiring careful review
3. **Complexity Trend** - Detect packages growing in complexity over time
4. **Authorship Analysis** - Understand who maintains each package
5. **Risk Scoring** - Calculate overall migration risk score

## Risk Factors

### 1. High Change Frequency
Packages modified frequently may have:
- Ongoing bug fixes (instability)
- Evolving requirements (scope creep)
- Technical debt accumulation

**Risk Level:** Medium-High

### 2. Recent Modifications
Packages changed within last 30-90 days:
- May have untested changes
- Could be mid-development
- Stakeholders may have pending requirements

**Risk Level:** High

### 3. Complexity Growth
Packages showing:
- Increasing task count over time
- Growing SQL statement size
- More precedence constraints

**Risk Level:** Medium

### 4. Multiple Authors
Packages with many contributors:
- Inconsistent coding styles
- Knowledge fragmentation
- Documentation gaps

**Risk Level:** Medium

### 5. No Recent Changes
Packages unchanged for years:
- May be deprecated but unclear
- Could have hidden dependencies
- Original authors unavailable

**Risk Level:** Low-Medium

## Usage Instructions

### 1. Analyze Single Package

```
Analyze change history risk for package [package_name].
```

### 2. Project-Wide Risk Assessment

```
Generate a risk assessment report for all packages in project [project_name].
```

### 3. Prioritize Migration Order

```
Recommend migration order based on risk analysis for [project_name].
```

### 4. Identify High-Risk Packages

```
List packages with high migration risk in [project_name] and explain why.
```

## Output Format

```yaml
risk_analysis:
  package: CustomerDataPipeline
  overall_risk_score: 0.72  # 0-1 scale
  risk_level: HIGH
  
  factors:
    change_frequency:
      score: 0.8
      weight: 0.25
      details:
        changes_last_90_days: 12
        changes_last_year: 45
        avg_monthly_changes: 3.75
        industry_benchmark: 1.0
        
    recency:
      score: 0.9
      weight: 0.30
      details:
        last_modified: "2024-01-10"
        days_since_change: 5
        modified_by: "developer@company.com"
        change_description: "Added new customer validation"
        
    complexity_trend:
      score: 0.6
      weight: 0.20
      details:
        task_count_growth: "+15% YoY"
        sql_complexity_growth: "+22% YoY"
        constraint_growth: "+10% YoY"
        
    authorship:
      score: 0.5
      weight: 0.15
      details:
        unique_authors: 4
        primary_author: "developer@company.com"
        author_available: true
        
    documentation:
      score: 0.7
      weight: 0.10
      details:
        has_readme: false
        inline_comments: "sparse"
        annotation_count: 3
        
  recommendations:
    - "HIGH PRIORITY: Package recently modified - verify latest changes are captured"
    - "Contact developer@company.com for knowledge transfer"
    - "Add extra test coverage due to high change frequency"
    - "Document business rules before migration"
    
  suggested_migration_phase: 3  # Later phase due to high risk
```

## Risk Scoring Formula

```
Risk Score = Σ(factor_score × weight)

Weights:
- Recency:           0.30 (most impactful)
- Change Frequency:  0.25
- Complexity Trend:  0.20
- Authorship:        0.15
- Documentation:     0.10

Risk Levels:
- LOW:    score < 0.3
- MEDIUM: score 0.3 - 0.6
- HIGH:   score > 0.6
```

## Change Detection Sources

### SSIS Package Metadata
```xml
<DTS:Property DTS:Name="CreationDate">2022-03-15T10:30:00</DTS:Property>
<DTS:Property DTS:Name="CreatorName">developer@company.com</DTS:Property>
<DTS:Property DTS:Name="LastModifiedProductVersion">15.0.2000</DTS:Property>
```

### Version Control (Git)
```bash
# Get change history
git log --oneline --follow -- "packages/CustomerDataPipeline.dtsx"

# Get change frequency
git log --since="1 year ago" --oneline -- "*.dtsx" | wc -l

# Get authors
git shortlog -sn -- "packages/CustomerDataPipeline.dtsx"
```

### File System
```python
# File modification time
import os
stat = os.stat("CustomerDataPipeline.dtsx")
modified_time = stat.st_mtime
```

## Migration Order Recommendations

Based on risk analysis:

| Phase | Risk Level | Package Types |
|-------|------------|---------------|
| 1 | Low | Stable, well-documented, no recent changes |
| 2 | Low-Medium | Infrequent changes, single author |
| 3 | Medium | Moderate changes, some complexity |
| 4 | Medium-High | Recent changes, multiple authors |
| 5 | High | Very active, complex, critical path |

## Integration

This skill integrates with:

- **SSIS Parser** - Extracts creation/modification metadata
- **Map Service** - Understands package dependencies for risk propagation
- **Sign-off Service** - Uses risk level for approval routing

## Best Practices

1. **Freeze Before Migration** - Stop changes to packages in migration
2. **Knowledge Transfer** - Interview authors of high-risk packages
3. **Parallel Testing** - Run source and target simultaneously for high-risk
4. **Phased Rollout** - Migrate low-risk first to build confidence
5. **Document Everything** - Capture institutional knowledge during migration
