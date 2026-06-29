# ETL Migration Reconciler

Compare source SSIS outputs with Databricks outputs to validate data integrity and transformation accuracy post-migration.

## When to Use

- Validating that migrated ETL produces identical results to source
- Identifying data discrepancies between source and target
- Certifying migration completeness before cutover
- Debugging transformation differences

## Capabilities

1. **Row Count Reconciliation** - Compare record counts between source and target
2. **Hash Comparison** - Detect data differences using row-level hashing
3. **Aggregate Validation** - Compare SUM, AVG, MIN, MAX for numeric columns
4. **Sample Comparison** - Detailed row-by-row comparison for discrepancy diagnosis
5. **Schema Drift Detection** - Identify column additions, removals, or type changes

## Reconciliation Strategies

### 1. Row Count Comparison
Fastest validation - confirms same number of records.

```sql
-- Source (SQL Server)
SELECT COUNT(*) as source_count FROM staging.orders

-- Target (Databricks)
SELECT COUNT(*) as target_count FROM silver.orders
```

### 2. Hash-Based Reconciliation
Detects any data differences using deterministic hashing.

```sql
-- Generate row hashes for comparison
-- SQL Server
SELECT 
    order_id,
    HASHBYTES('SHA2_256', 
        CONCAT(order_id, '|', customer_id, '|', CAST(amount AS VARCHAR))
    ) as row_hash
FROM staging.orders

-- Databricks
SELECT 
    order_id,
    sha2(concat_ws('|', order_id, customer_id, cast(amount as string)), 256) as row_hash
FROM silver.orders
```

### 3. Aggregate Comparison
Validates numeric transformations and calculations.

```sql
-- Compare aggregates
SELECT 
    'source' as system,
    COUNT(*) as row_count,
    SUM(amount) as total_amount,
    AVG(amount) as avg_amount,
    MIN(order_date) as min_date,
    MAX(order_date) as max_date
FROM source_orders

UNION ALL

SELECT 
    'target' as system,
    COUNT(*),
    SUM(amount),
    AVG(amount),
    MIN(order_date),
    MAX(order_date)
FROM target_orders
```

### 4. Key-Based Diff
Identify specific records that differ.

```sql
-- Find missing records in target
SELECT order_id, 'MISSING_IN_TARGET' as issue
FROM source_orders s
WHERE NOT EXISTS (
    SELECT 1 FROM target_orders t WHERE t.order_id = s.order_id
)

UNION ALL

-- Find extra records in target
SELECT order_id, 'EXTRA_IN_TARGET' as issue
FROM target_orders t
WHERE NOT EXISTS (
    SELECT 1 FROM source_orders s WHERE s.order_id = t.order_id
)
```

## Usage Instructions

### 1. Run Full Reconciliation

```
Reconcile data between SSIS package [package_name] outputs and Databricks tables.
```

### 2. Quick Count Check

```
Compare row counts for all tables loaded by [package_name].
```

### 3. Investigate Discrepancy

```
Diagnose data differences in [table_name] between source and target.
```

### 4. Generate Reconciliation Report

```
Generate a reconciliation certification report for [package_name] migration.
```

## Output Format

```yaml
reconciliation_report:
  package: CustomerDataPipeline
  execution_time: "2024-01-15T14:30:00Z"
  overall_status: PARTIAL_MATCH
  
  tables:
    - table: orders
      status: MATCH
      source_count: 1500000
      target_count: 1500000
      count_match: true
      hash_match: true
      aggregate_validation:
        total_amount: 
          source: 45678901.23
          target: 45678901.23
          difference: 0.00
          status: MATCH

    - table: order_lines
      status: MISMATCH
      source_count: 4500000
      target_count: 4499850
      count_match: false
      difference: 150
      diagnosis:
        missing_in_target: 150
        extra_in_target: 0
        sample_missing_keys: [123456, 123457, 123458, "..."]
      root_cause_hints:
        - "150 records have NULL product_id in source"
        - "Target has NOT NULL constraint on product_id"
        - "Recommend: Add COALESCE or filter in transformation"

  summary:
    tables_validated: 5
    tables_matched: 3
    tables_mismatched: 2
    total_discrepancies: 150
```

## Tolerance Settings

Some reconciliation scenarios require tolerance:

```yaml
tolerance_settings:
  # Floating point comparison tolerance
  numeric_tolerance: 0.01  # Allow 1% difference
  
  # Date/time comparison tolerance
  timestamp_tolerance: "1 second"  # Allow 1 second drift
  
  # Count tolerance for append-only tables
  count_tolerance: 0  # Exact match required
  
  # Allow known exclusions
  excluded_records:
    - filter: "is_test = 1"
      reason: "Test records excluded from migration"
```

## Common Discrepancy Causes

| Issue | Symptom | Solution |
|-------|---------|----------|
| NULL handling | Counts match, hashes differ | Use COALESCE consistently |
| Floating point | Aggregates slightly differ | Apply rounding, use tolerance |
| Timezone | Timestamps shifted | Standardize to UTC |
| Character encoding | Text data differs | Normalize encoding |
| Trailing spaces | String hashes differ | TRIM all string columns |
| Case sensitivity | Lookups fail | Standardize case |

## Integration

This skill integrates with:

- **Reconciliation Service** - Backend comparison engine
- **Data Pattern Classifier** - Understands expected transformation behavior
- **Sign-off Service** - Gates migration based on reconciliation results

## Reconciliation Checklist

Before certification:

- [ ] All tables have row count match
- [ ] Hash comparison passes for sampled records
- [ ] Aggregate validations pass within tolerance
- [ ] No unexpected schema differences
- [ ] Business-critical columns validated
- [ ] Historical data spot-checked
- [ ] Edge cases tested (NULLs, empty strings, extremes)

## Best Practices

1. **Automate Reconciliation** - Build into CI/CD pipeline
2. **Document Tolerances** - Explain why tolerances are acceptable
3. **Sample Large Tables** - Full hash comparison may be impractical
4. **Test Edge Cases** - NULLs, empty strings, boundary values
5. **Archive Evidence** - Keep reconciliation reports for audit
