# Contract-Driven Architecture — Unified Study

> Contratos como o glue entre componentes. Todo integration point é um contrato. Todo contrato é código. Todo contrato é testável.
> Data: 2026-05-29 | Status: Study
> Cross-cuts: poc-architecture-standards.md (Cat 1-8), data4u-contract-format.md, tooling-study.md

---

## 1. Why Contracts Matter

**Problem**: Components integrate through implicit assumptions — column names, API shapes, event schemas, type mappings. When any assumption changes, integration breaks silently. In a migration (HAE), this is amplified: legacy and target coexist, and every boundary is in flux.

**Solution**: Make every integration point explicit as a contract. Contracts are:
- **Authoritative** — the contract IS the spec, not the implementation
- **Testable** — contract tests catch breaking changes before they reach production
- **Generative** — code, types, docs, and tests can be generated FROM the contract
- **Versioned** — schema evolution is explicit, not accidental
- **Bilateral** — producer and consumer both validate against the same contract

**ROI for HAE Migration**:
| Without Contracts | With Contracts |
|-------------------|----------------|
| Schema drift detected in production (hours/days) | Schema drift detected in CI (minutes) |
| API breaking changes found by consumers | Breaking changes blocked at PR |
| Frontend-backend misalignment = runtime errors | Type-safe generated clients = compile-time errors |
| dbt model changes break downstream silently | dbt contracts + refs enforce dependency integrity |
| Event schema changes break consumers | Schema Registry compatibility check blocks deploy |

---

## 2. Contract Taxonomy

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTRACT TYPES                               │
├─────────────────┬───────────────────┬───────────────────────────┤
│  DATA LAYER     │  API LAYER        │  EVENT LAYER              │
│                 │                   │                           │
│  • Data 4U      │  • OpenAPI 3.1    │  • AsyncAPI 2.6          │
│  • dbt model    │  • gRPC/Protobuf  │  • Schema Registry       │
│  • Data Contract│  • GraphQL schema │  • CloudEvents           │
│    Specification│  • JSON:API       │  • Debezium CDC          │
│                 │                   │                           │
├─────────────────┼───────────────────┼───────────────────────────┤
│  UI LAYER       │  INTEGRATION      │  MIGRATION LAYER         │
│                 │                   │                           │
│  • Design tokens│  • Pact (CDC)     │  • Data 4U (source→target)│
│  • Component    │  • MCP protocol   │  • sqlglot (T-SQL→Spark) │
│    props/API    │  • Agent I/O spec │  • Technology profile    │
│  • Storybook    │  • Airflow DAG    │  • Migration item spec   │
│    stories      │    interface      │  • Context snapshot spec  │
└─────────────────┴───────────────────┴───────────────────────────┘
```

### 2.1 Contract Boundaries in HAE Architecture

```
                    ┌──────────────┐
                    │  Power BI    │  ← UI contract (dataset schema)
                    └──────┬───────┘
                           │ C6: Dataset contract
                    ┌──────▼───────┐
                    │  Gold Layer  │  ← Data contract (dbt model contract)
                    └──────┬───────┘
                           │ C5: dbt ref() contract
                    ┌──────▼───────┐
                    │ Silver Layer │  ← Data contract (dbt model contract)
                    └──────┬───────┘
                           │ C4: dbt ref() contract
                    ┌──────▼───────┐
                    │ Bronze Layer │  ← Data 4U contract (source→raw)
                    └──────┬───────┘
                           │ C3: Source contract (dbt sources.yml)
                    ┌──────▼───────┐
                    │  SQL Server  │  ← Legacy schema (implicit contract)
                    └──────────────┘

    ┌──────────────┐    C1: API contract     ┌──────────────┐
    │  Frontend    │◄──────OpenAPI 3.1──────►│  Backend API │
    └──────────────┘                         └──────┬───────┘
                                                    │ C2: Event contract
                                             ┌──────▼───────┐
                                             │  Event Bus   │
                                             │  (Kafka/EH)  │
                                             └──────────────┘

    ┌──────────────┐    C7: MCP protocol     ┌──────────────┐
    │  AI Agent    │◄──────tool I/O spec────►│  MCP Server  │
    └──────────────┘                         └──────────────┘
```

Each **C1-C7** is a contract boundary that must be:
1. **Specified** — explicit schema/format
2. **Validated** — automated contract tests in CI
3. **Versioned** — semantic versioning with compatibility rules
4. **Documented** — generated docs from contract, not separate wiki

---

## 3. Data Layer Contracts

### 3.1 Data 4U Contract (already studied)

See `data4u-contract-format.md` for full structure. Key properties:
- **Scope**: Source table → Bronze → Silver → Gold (full medallion path)
- **Authority**: Data 4U catalog is the single source of truth
- **Generative**: Contract → dbt models + tests + schema.yml (via data4u-mcp)
- **Drift-detectable**: `diff_contracts` tool compares contract vs actual schema

### 3.2 Data Contract Specification (emerging standard)

The [Data Contract Specification](https://datacontract.com/) is an open standard (by Jochen Christ) gaining adoption. It complements Data 4U by providing a vendor-neutral format.

| Aspect | Data 4U Contract | Data Contract Specification |
|--------|-----------------|---------------------------|
| Origin | HAE-proprietary | Open standard |
| Scope | Full migration (source→target) | Data product interface (output only) |
| Format | YAML (hypothesized) | YAML (specified) |
| Schema definition | Inline columns | JSON Schema / dbt / BigQuery |
| Quality rules | Inline expectations | SodaCL / Great Expectations refs |
| Examples | HAE-specific | Public examples available |
| Tooling | Custom MCP server | `datacontract-cli` (validation, breaking change) |

**Recommendation**: Use Data 4U as the **migration contract** (source→target mapping) and Data Contract Specification as the **product contract** (output interface for consumers). They compose:

```
Data 4U contract (migration spec)
  └── generates → Data Contract Specification (product interface)
                    └── consumed by → downstream teams, Power BI, APIs
```

Example Data Contract Specification for HAE Gold layer:

```yaml
dataContractSpecification: 0.9.2
id: hae-clinical-patient-demographics
version: 1.0.0
name: Patient Demographics
description: SCD2 dimension for patient demographics (Gold layer)

server:
  type: databricks
  host: adb-xxx.azuredatabricks.net
  catalog: hae_lakehouse
  schema: gold_clinical

models:
  dim_patient:
    description: Patient demographics dimension (SCD Type 2)
    type: table
    fields:
      patient_sk:
        type: bigint
        description: Surrogate key
        primaryKey: true
      patient_id:
        type: bigint
        description: Natural key from source
      patient_name:
        type: string
        description: Patient full name
        pii: true
        classification: nome
      cpf:
        type: string
        description: Brazilian tax ID
        pii: true
        classification: cpf
        masked: true
      birth_date:
        type: timestamp
        description: Date of birth
        pii: true
        classification: data_nascimento
      gender_code:
        type: string
        description: Gender code
        constraints:
          - type: accepted-values
            values: ["M", "F", "O", "U"]
      eff_start_date:
        type: timestamp
        description: SCD2 valid from
      eff_end_date:
        type: timestamp
        description: SCD2 valid to
      is_current:
        type: boolean
        description: SCD2 current flag

quality:
  type: SodaCL
  specification:
    checks for dim_patient:
      - row_count > 0
      - missing(patient_id) = 0
      - uniqueness(patient_id)
      - missing(patient_sk) = 0
      - uniqueness(patient_sk)
      - values in (gender_code) must be in (M, F, O, U)

servicelevel:
  availability: 99.9%
  freshness: 24h
```

### 3.3 dbt Model Contracts (built-in)

dbt-core 1.5+ supports `contract.enforced` on models — this makes the model's schema.yml a runtime contract:

```yaml
# models/gold/clinical/dim_patient.yml
models:
  - name: dim_patient
    config:
      contract:
        enforced: true
    columns:
      - name: patient_sk
        data_type: bigint
        constraints:
          - type: primary_key
          - type: not_null
      - name: patient_id
        data_type: bigint
        constraints:
          - type: not_null
          - type: unique
      - name: patient_name
        data_type: string
      - name: cpf
        data_type: string
        meta:
          pii: true
          classification: cpf
          masked: true
```

**What `contract.enforced: true` does**:
1. At `dbt run`, validates that the model's actual columns + types match schema.yml
2. Fails the run if columns are missing, extra, or type-mismatched
3. Prevents silent schema drift between contract and implementation

**HAE Application**: Every Gold layer model should have `contract.enforced: true`. Silver models should have it after initial stabilization. Bronze models should NOT (source schema may vary).

### 3.4 dbt Sources Contract (schema-on-read boundary)

The `sources.yml` file IS the contract between external systems and the dbt project:

```yaml
# models/staging/sources.yml
version: 2

sources:
  - name: sqlserver_dw
    database: DW_Corporativo
    schema: dbo
    tables:
      - name: tbl_pacientes
        description: Patient demographics (source system)
        columns:
          - name: CD_PACIENTE
            description: Patient surrogate key
            tests:
              - not_null
              - unique
          - name: NM_PACIENTE
            description: Patient full name
            meta:
              pii: true
        freshness:
          warn_after: {count: 24, period: hour}
          error_after: {count: 48, period: hour}
          filter: DT_ALTERACAO > '2020-01-01'
```

**Key insight**: `sources.yml` + `freshness` = a **data SLA contract**. If the source stops updating, dbt alerts. This is the boundary between "we don't control the source" and "we must guarantee our pipeline input".

---

## 4. API Layer Contracts

### 4.1 OpenAPI 3.1 (REST API Contract)

OpenAPI is the contract between backend and frontend (and between microservices).

**HAE Application**: Einstein's patient portal, scheduling API, billing API — each needs a contract.

```yaml
# openapi/patient-api.yaml
openapi: 3.1.0
info:
  title: Patient Demographics API
  version: 1.2.0
paths:
  /patients/{patientId}:
    get:
      operationId: getPatient
      parameters:
        - name: patientId
          in: path
          required: true
          schema:
            type: integer
            format: int64
      responses:
        "200":
          description: Patient demographics
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/PatientDemographics"
        "404":
          $ref: "#/components/responses/NotFound"

components:
  schemas:
    PatientDemographics:
      type: object
      required: [patientId, patientName, genderCode]
      properties:
        patientId:
          type: integer
          format: int64
          description: Natural key from source system
        patientName:
          type: string
          maxLength: 200
          x-pii: true
          x-classification: nome
        cpf:
          type: string
          pattern: "^[0-9]{11}$"
          x-pii: true
          x-classification: cpf
          x-masked: true
        genderCode:
          type: string
          enum: [M, F, O, U]
```

**Code generation from contract**:
```
OpenAPI spec → TypeScript types (frontend)
            → Pydantic models (backend)
            → Server stubs (FastAPI route scaffolding)
            → Contract tests (Schemathesis)
            → Documentation (Redoc/SwaggerUI)
```

### 4.2 Consumer-Driven Contract Testing (Pact)

Pact flips the direction: the **consumer** defines what it needs, and the **producer** must satisfy all consumers.

```
┌──────────┐  "I need GET /patients/{id} returning  ┌──────────┐
│ Frontend │ ── {patientId, name, gender} ────────► │ Backend  │
│ (consumer│    Pact interaction                     │ (provider│
│  test)   │                                       │  verify) │
└──────────┘                                       └──────────┘
```

**Workflow**:
1. Frontend team writes Pact test defining expected API shape
2. Pact publishes interaction to Pact Broker
3. Backend CI runs `pact-verifier` against the broker
4. If backend breaks the contract, CI fails BEFORE merge

**HAE Application**: Critical for the migration period when frontend talks to both legacy and new APIs. Pact ensures the new API is compatible before cutting over.

### 4.3 gRPC/Protobuf (Service-to-Service Contract)

For internal service-to-service communication where performance matters:

```protobuf
// patient_service.proto
syntax = "proto3";
package hae.clinical.v1;

service PatientService {
  rpc GetPatient(GetPatientRequest) returns (PatientDemographics);
  rpc ListPatients(ListPatientsRequest) returns (stream PatientSummary);
}

message PatientDemographics {
  int64 patient_id = 1;
  string patient_name = 2 [(pii) = true];
  string cpf = 3 [(pii) = true, (masked) = true];
  GenderCode gender_code = 4;
  google.protobuf.Timestamp birth_date = 5 [(pii) = true];
}

enum GenderCode {
  GENDER_CODE_UNSPECIFIED = 0;
  GENDER_CODE_M = 1;
  GENDER_CODE_F = 2;
  GENDER_CODE_O = 3;
  GENDER_CODE_U = 4;
}
```

**Advantage over OpenAPI for internal APIs**:
- Binary wire format (smaller, faster)
- Strong types in 11+ languages (auto-generated)
- Backward compatibility built into Protobuf rules (don't reuse field numbers)
- Schema Registry compatible (Confluent supports Protobuf natively)

---

## 5. Event Layer Contracts

### 5.1 AsyncAPI 2.6 (Event API Contract)

AsyncAPI is to events what OpenAPI is to REST — a machine-readable spec for event-driven interfaces.

```yaml
# asyncapi/patient-events.yaml
asyncapi: 2.6.0
info:
  title: Patient Domain Events
  version: 1.0.0
channels:
  patient.demographics.updated:
    publish:
      message:
        $ref: "#/components/messages/PatientDemographicsUpdated"
  patient.admitted:
    publish:
      message:
        $ref: "#/components/messages/PatientAdmitted"

components:
  messages:
    PatientDemographicsUpdated:
      name: patient.demographics.updated
      title: Patient demographics changed
      payload:
        $ref: "#/components/schemas/PatientDemographicsEvent"
  schemas:
    PatientDemographicsEvent:
      type: object
      required: [eventId, patientId, updatedAt]
      properties:
        eventId:
          type: string
          format: uuid
        patientId:
          type: integer
          format: int64
        updatedFields:
          type: array
          items:
            type: string
        updatedAt:
          type: string
          format: date-time
```

### 5.2 Schema Registry + Compatibility Modes

The Schema Registry enforces contract evolution rules at deploy time:

| Compatibility Mode | Allows | Blocks | Use When |
|-------------------|--------|--------|----------|
| **BACKWARD** | Add optional fields, remove fields | Add required field, remove optional field | Consumers tolerate new fields (most common) |
| **FORWARD** | Add required field, remove optional field | Add optional field, remove field | Producers don't know all consumers |
| **FULL** | Only additive optional changes | Any breaking change | Critical streams (patient data) |
| **NONE** | Anything | Nothing | Development only |

**HAE Recommendation**: `FULL` compatibility for clinical event streams (patient data must never break consumers). `BACKWARD` for operational/financial streams.

### 5.3 CloudEvents (Event Envelope Contract)

Standardizes the envelope so all events share a common shape:

```json
{
  "specversion": "1.0",
  "type": "com.hae.clinical.patient.demographics.updated",
  "source": "/patients/demographics",
  "id": "A234-1234-1234",
  "time": "2026-05-29T17:31:00Z",
  "datacontenttype": "application/avro",
  "data": { "...": "..." }
}
```

---

## 6. Frontend-Backend Contracts

### 6.1 OpenAPI → TypeScript (Type-Safe Frontend)

The single biggest code quality improvement for frontend: **generate types from the API contract, never hand-write them**.

```bash
# Generate TypeScript client from OpenAPI spec
npx openapi-typescript openapi/patient-api.yaml -o src/types/patient-api.ts
```

```typescript
// src/types/patient-api.ts (GENERATED — never edit)
export interface PatientDemographics {
  patientId: number;
  patientName: string;
  cpf?: string;        // masked in response
  genderCode: "M" | "F" | "O" | "U";
  birthDate?: string;
}

// src/api/patients.ts (hand-written, using generated types)
import type { PatientDemographics } from "../types/patient-api";

async function getPatient(id: number): Promise<PatientDemographics> {
  const res = await fetch(`/api/patients/${id}`);
  return res.json(); // TypeScript validates shape at compile time
}
```

**If the backend adds a required field without updating the contract**: Frontend CI fails (type mismatch). If the contract is updated first, frontend CI generates new types and shows the compile error. Either way, **the mismatch is caught before deployment**.

### 6.2 Design Tokens as UI Contract

Design tokens bridge design and engineering — they are the contract between Figma and code:

```json
{
  "color": {
    "clinical": {
      "critical": { "value": "#DC2626", "type": "color" },
      "warning":  { "value": "#F59E0B", "type": "color" },
      "normal":   { "value": "#10B981", "type": "color" }
    }
  },
  "spacing": {
    "unit": { "value": "4px", "type": "dimension" }
  }
}
```

**Workflow**: Figma → Design Tokens (JSON) → Style Dictionary → CSS Variables / Tailwind config / Android XML / iOS Swift. Same source, all platforms.

### 6.3 Component Props as Contract (Storybook + TS)

Each UI component's props are a contract with its consumers:

```typescript
// PatientCard.props.ts (contract)
interface PatientCardProps {
  patientId: number;
  patientName: string;
  genderCode: "M" | "F" | "O" | "U";
  admissionDate?: Date;
  status: "active" | "discharged" | "transferred";
  onClick?: (patientId: number) => void;
}
```

Storybook stories serve as **visual contract tests** — they document the expected rendering for each prop combination and catch visual regressions.

---

## 7. Schema Evolution — How Contracts Change Over Time

Contracts are not static. The key question is: **how do you change a contract without breaking consumers?**

### 7.1 Evolution Strategies

| Strategy | Rule | Example | Risk |
|----------|------|---------|------|
| **Additive** | Only add optional fields | Add `middleName?: string` to PatientDemographics | Safest — backward compatible |
| **Deprecation** | Mark field deprecated, remove later | `@deprecated cpf — use taxId instead` | Safe if consumers don't use field |
| **Widening** | Relax constraints | Change `maxLength: 100` to `maxLength: 200` | Safe — more values accepted |
| **Narrowing** | Tighten constraints | Change `maxLength: 200` to `maxLength: 100` | **Breaking** — existing data may violate |
| **Type change** | Change field type | `string` → `integer` for phone number | **Breaking** — must version the contract |
| **Rename** | Change field name | `patientName` → `fullName` | **Breaking** — use additive + deprecation |

### 7.2 Versioning Schemes

| Scheme | Format | When to Use | Example |
|--------|--------|-------------|---------|
| **Semantic** | MAJOR.MINOR.PATCH | API contracts, data contracts | `1.2.0` → `1.3.0` (additive), `2.0.0` (breaking) |
| **Date-based** | YYYY-MM-DD | Event schemas, daily snapshots | `2026-05-29` |
| **Suffix** | v1, v2 in URL/path | REST APIs | `/api/v2/patients` |
| **Protocol-native** | Protobuf field numbers | gRPC services | Never reuse field number 5 |

### 7.3 Delta Lake Schema Evolution (Data Layer)

Delta Lake supports schema evolution at the table level — this is the data contract evolution mechanism for the Lakehouse:

```python
# Enable schema evolution on merge
spark.sql("""
MERGE INTO hae_lakehouse.gold_clinical.dim_patient target
USING stg_patients source
ON target.patient_id = source.patient_id
WHEN MATCHED AND source.updated_at > target.updated_at THEN
  UPDATE SET *
WHEN NOT MATCHED THEN
  INSERT *
""").schemaEvolutionMode("addNewColumns")  # additive only
```

**HAE Rule**: Schema evolution on Gold tables = `addNewColumns` only. Never drop or rename columns in-place. Use deprecation metadata + views for backward compatibility.

---

## 8. Integration Contracts (MCP + Agent + Pipeline)

### 8.1 MCP Protocol as Contract

Every MCP server exposes a contract via its tool definitions. The MCP protocol itself is the meta-contract:

```python
# Every MCP tool IS a contract:
@mcp.tool
async def ingest_contract(contract_path: str) -> ContractParseResult:
    """
    Contract:
    - Input: contract_path (str) — path to YAML/JSON file
    - Output: ContractParseResult {contract_id, entity_name, columns, ...}
    - Side effects: None (pure read + parse)
    - Error: FileNotFoundError, ValidationError
    """
```

**Cross-server contracts**: When `dbt-extended-mcp.contract_to_dbt_bridge` calls `data4u-mcp.ingest_contract`, there is an implicit contract on the return type. This should be made explicit:

```
data4u-mcp.ingest_contract → ContractParseResult
                                ↓ (must match)
dbt-extended-mcp.contract_to_dbt_bridge expects: ContractParseResult
```

**Enforcement**: Pydantic models shared between servers define the contract types. Any mismatch = import error at startup.

### 8.2 Agent I/O Specification

Each AI agent has an input/output contract (from spike plan):

| Agent | Input Contract | Output Contract | Side Effects |
|-------|---------------|-----------------|--------------|
| Schema Mapper | Data 4U contract + source schema | Column mapping suggestions | Read-only |
| SSIS Analyzer | .dtsx file path | DataFlow[] + MigrationPlan | Read-only |
| dbt Generator | Data 4U contract + mapping | dbt model files | **Write** (HITL gate) |
| DQ Validator | dbt manifest + rules | Check results | Read-only |

**Write agents must go through HITL gate** — the contract includes a `requires_approval: true` flag. The agent proposes, human approves, then write is executed.

### 8.3 Airflow DAG Interface Contract

Each Airflow DAG has an implicit contract with upstream/downstream DAGs:

```python
# Explicit DAG contract
class DagContract:
    dag_id: str
    expected_inputs: list[TableFQN]     # tables this DAG reads
    guaranteed_outputs: list[TableFQN]   # tables this DAG writes
    sla: timedelta                       # max execution time
    freshness_sla: timedelta             # max data age
    owner: str                           # team responsible
```

This makes cross-DAG dependencies explicit and testable. If DAG A guarantees `gold_clinical.dim_patient` with freshness 24h, DAG B that reads it can set its sensor timeout accordingly.

---

## 9. Contract Lifecycle

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  AUTHOR  │───►│ VALIDATE │───►│ VERSION  │───►│  EVOLVE  │───►│DEPRECATE │
│          │    │          │    │          │    │          │    │          │
│ Write    │    │ Lint +   │    │ SemVer   │    │ Additive │    │ Mark     │
│ contract │    │ test +   │    │ tag +    │    │ changes  │    │ @deprecated│
│ in YAML/ │    │ breaking │    │ changelog│    │ only;    │    │ + sunset │
│ JSON/    │    │ change   │    │ +        │    │ version  │    │ date     │
│ Proto    │    │ detect   │    │ publish  │    │ bump     │    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
      │               │               │               │               │
      ▼               ▼               ▼               ▼               ▼
   Git repo        CI pipeline    Schema Reg.     CI pipeline     Sunset PR
   (source of      (gate on PR)  / Pact Broker   (compat check)  (remove code)
    truth)
```

### 9.1 CI/CD Gates by Contract Type

| Contract Type | CI Gate | Failure Mode | Blocking? |
|--------------|---------|-------------|-----------|
| OpenAPI | `spectral lint` + breaking change diff | PR comment with violations | Yes |
| Data Contract Spec | `datacontract verify` + breaking change | PR comment | Yes |
| dbt model contract | `dbt run` contract enforcement | Pipeline failure | Yes |
| Pact | `pact-verifier` against broker | Provider verification fails | Yes |
| Event schema | Schema Registry compatibility check | Deploy rejected | Yes |
| MCP tool spec | Pydantic validation at server startup | Server fails to start | Yes |
| Design tokens | Style Dictionary build | Build failure | Yes |

---

## 10. Tooling Summary

| Tool | Contract Type | Purpose | License |
|------|--------------|---------|---------|
| `datacontract-cli` | Data Contract Spec | Validate, diff, breaking change detection | MIT |
| `openapi-typescript` | OpenAPI → TS | Generate TypeScript types from API spec | MIT |
| `openapi-python-client` | OpenAPI → Python | Generate Pydantic models + httpx client | MIT |
| `spectral` | OpenAPI | Lint API spec against best practices | Apache 2.0 |
| `schemathesis` | OpenAPI | Fuzz test API against its spec | Apache 2.0 |
| `pact-python` / `pact-js` | Pact | Consumer-driven contract testing | MIT |
| `pact-broker` | Pact | Share + verify Pact interactions | MIT |
| `asyncapi-generator` | AsyncAPI | Generate docs, code, TypeScript types | Apache 2.0 |
| `apicurio-registry` | Schema Registry | Store + validate Avro/Protobuf/JSON Schema | Apache 2.0 |
| `sqlglot` | SQL schema | Transpile + diff SQL schemas | Apache 2.0 |
| `dbt-core` (contract.enforced) | dbt model | Runtime contract enforcement | Apache 2.0 |
| `style-dictionary` | Design tokens | Generate CSS/TS/Swift from tokens | Apache 2.0 |
| `schemachange` | Database schema | Version-controlled DDL migrations | Apache 2.0 |

---

## 11. HAE Application — Where Each Contract Applies

| HAE Component | Contract Type | Tool | Priority |
|--------------|--------------|------|----------|
| SQL Server → Bronze (source ingestion) | Data 4U contract + dbt sources.yml | data4u-mcp + dbt | P0 |
| Bronze → Silver → Gold (transformation) | dbt model contract (enforced) | dbt-core 1.5+ | P0 |
| Gold → Power BI (consumption) | Data Contract Specification | datacontract-cli | P1 |
| Gold → API (exposure) | OpenAPI 3.1 | openapi-typescript, spectral | P1 |
| API → Frontend (patient portal) | OpenAPI → TypeScript types | openapi-typescript | P1 |
| Frontend components | Component props + Storybook | TypeScript + Storybook | P2 |
| Event streams (patient events) | AsyncAPI + Schema Registry | apicurio-registry | P2 |
| MCP server tool interfaces | Pydantic I/O models | FastMCP | P1 |
| Agent I/O contracts | Pydantic + HITL gate | FastMCP + LangFuse | P1 |
| Airflow DAG dependencies | DagContract (explicit) | Airflow + custom | P2 |
| Design system | Design tokens | Style Dictionary | P3 |
| SSIS → Databricks (migration) | Data 4U contract + sqlglot | data4u-mcp + sqlglot | P0 |

---

## 12. Recommendations

### 12.1 Immediate (Spike 1-2)

1. **Enable `contract.enforced: true` on all Gold models** — zero-effort, built into dbt-core
2. **Add `sources.yml` with freshness for all Bronze sources** — data SLA contract for free
3. **Use sqlglot for T-SQL→Spark SQL transpilation** — every transpiled query IS a contract check (if sqlglot can parse it, the schema is valid)

### 12.2 Short-term (Spike 3-4)

4. **Build data4u-mcp with contract validation** — every contract is validated before dbt generation
5. **Generate Data Contract Specification from Gold models** — `dbt model → datacontract YAML` for downstream consumers
6. **Add `datacontract verify` to CI** — breaking change detection on every PR that touches Gold models
7. **Define MCP tool I/O contracts as shared Pydantic models** — type safety across all 4 custom servers

### 12.3 Medium-term (Post-spike)

8. **OpenAPI spec for any API that reads Gold layer** — patient portal, scheduling, billing
9. **`openapi-typescript` for frontend** — generate types, never hand-write
10. **Pact tests for frontend↔backend** — especially during migration cutover
11. **Schema Registry for event streams** — FULL compatibility for clinical, BACKWARD for others
12. **AsyncAPI spec for all Kafka/EventHub topics** — event contract as code

### 12.4 Long-term (Enterprise maturity)

13. **Design tokens from Figma** — single source for all platforms
14. **DagContract for all Airflow DAGs** — explicit cross-DAG dependencies
15. **Contract catalog** — single place to browse all contracts (Backstage plugin or custom)
16. **Contract coverage metric** — % of integration points covered by explicit contracts (target: >90%)

### 12.5 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Contract authority for data | Data 4U catalog | Already the source of truth in HAE process |
| Contract authority for APIs | OpenAPI spec in Git | Version-controlled, reviewable, CI-enforced |
| Contract format for events | Avro + Schema Registry | Compact binary, evolution rules built-in |
| Contract enforcement level | Fail CI on breaking change | Silent drift is worse than blocked PR |
| Generate or hand-write types? | **Always generate** | Hand-written types always drift from reality |
| dbt contract enforcement | Gold=enforced, Silver=after stabilize, Bronze=off | Source schema is not under our control |
| Schema evolution mode | Additive only on Gold | Breaking changes need new version, not mutation |

---

## 13. References

- `data4u-contract-format.md` — Data 4U contract hypothesized structure
- `tooling-study.md` — MCP server + framework tooling
- `context-management-universal.md` — Generic context management (migration_item contracts)
- `poc-architecture-standards.md` — Cat 1 (API contracts), Cat 3 (Schema Registry), Cat 6 (data quality as contract)
- `hae-migration-ai-spike-plan.md` — Spike plan with agent I/O specs
- [Data Contract Specification](https://datacontract.com/) — Open standard for data product contracts
- [Pact](https://pact.io/) — Consumer-driven contract testing
- [AsyncAPI](https://www.asyncapi.com/) — Event API specification
