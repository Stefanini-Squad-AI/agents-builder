# Business Rules Compliance Analyzer

Analyze SSIS packages to extract and validate business rules embedded in ETL logic, ensuring compliance during Databricks migration.

## When to Use

- Validating that business rules from source SSIS packages are preserved in migrated code
- Extracting embedded business logic from SQL transformations
- Documenting business rule inventory for compliance audits
- Identifying undocumented business rules hidden in ETL code

## Capabilities

This skill analyzes SSIS package SQL statements to:

1. **Extract Business Rules** - Identify CASE/WHEN logic, validation checks, data transformations
2. **Classify Rule Types** - Categorize rules as validation, transformation, derivation, or filtering
3. **Map Dependencies** - Track which tables/columns each rule affects
4. **Generate Documentation** - Produce compliance-ready rule inventory

## Rule Detection Patterns

### Validation Rules
```sql
-- NULL checks
WHERE column IS NOT NULL

-- Range validation  
WHERE amount BETWEEN 0 AND 1000000

-- Pattern validation
WHERE email LIKE '%@%.%'

-- Referential integrity
WHERE customer_id IN (SELECT id FROM customers)
```

### Transformation Rules
```sql
-- Derived columns
CASE WHEN status = 'A' THEN 'Active' ELSE 'Inactive' END

-- Calculations
unit_price * quantity * (1 - discount) AS line_total

-- Type conversions
CAST(date_string AS DATE)
```

### Filtering Rules
```sql
-- Date filters
WHERE transaction_date >= DATEADD(month, -12, GETDATE())

-- Status filters
WHERE is_deleted = 0 AND is_active = 1

-- Regional filters
WHERE region_code IN ('US', 'CA', 'MX')
```

## Usage Instructions

### 1. Run Analysis

To analyze a package's business rules:

```
Analyze the business rules in package [package_name] and generate a compliance report.
```

### 2. Compare Pre/Post Migration

```
Compare business rules between the original SSIS package and the generated Databricks code for [package_name].
```

### 3. Generate Rule Inventory

```
Generate a business rules inventory document for all packages in project [project_name].
```

## Output Format

The skill produces a structured analysis:

```yaml
package: DailyOrderProcessing
rules_found: 15
rules_by_type:
  validation: 6
  transformation: 5
  derivation: 2
  filtering: 2

rules:
  - id: BR-001
    type: validation
    description: "Order amount must be positive"
    source_task: "Validate Orders"
    sql_pattern: "WHERE order_amount > 0"
    affected_tables: [orders, order_lines]
    criticality: high
    
  - id: BR-002
    type: transformation
    description: "Calculate order total with tax"
    source_task: "Calculate Totals"
    sql_pattern: "subtotal * (1 + tax_rate) AS total"
    affected_columns: [subtotal, tax_rate, total]
    criticality: medium
```

## Compliance Mapping

| Source Pattern | Databricks Equivalent | Migration Notes |
|----------------|----------------------|-----------------|
| CASE WHEN | CASE WHEN | Direct translation |
| ISNULL() | COALESCE() | Use COALESCE for multiple fallbacks |
| GETDATE() | current_timestamp() | Databricks timestamp function |
| DATEADD() | date_add() / add_months() | Different function names |
| CONVERT() | CAST() | Use CAST with date formats |

## Integration

This skill integrates with:

- **Data Pattern Classifier** - Understands context of where rules are applied
- **Reconciliation Service** - Validates rule preservation post-migration
- **Documentation Generator** - Embeds rule documentation in notebooks

## Best Practices

1. **Document Everything** - Even simple rules deserve documentation
2. **Test Boundary Cases** - Business rules often have edge cases
3. **Maintain Traceability** - Link each migrated rule to its source
4. **Version Rules** - Track rule changes across migrations
