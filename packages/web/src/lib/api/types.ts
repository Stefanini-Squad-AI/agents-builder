// TypeScript types matching backend Pydantic models
// Generated from packages/core/app/schemas/views.py and app/enums.py

// Enums
export enum ProjectStatus {
  DRAFT = "draft",
  IN_PROGRESS = "in_progress",
  EXPORTED = "exported",
  ARCHIVED = "archived",
}

export enum ProjectType {
  APPLICATION = "application",
  MIGRATION = "migration",
}

export enum CardTemplate {
  PHASE_VLI = "phase_vli",
  MIGRATION = "migration",
  STRICT_9 = "strict_9",
  FREE_FORM = "free_form",
}

export enum Grouping {
  PHASE = "phase",
  EPIC = "epic",
  FLAT = "flat",
}

export enum LlmProvider {
  ANTHROPIC = "anthropic",
  OPENAI = "openai",
  OLLAMA = "ollama",
  BEDROCK = "bedrock",
}

export enum ArtifactKind {
  DOC = "doc",
  CODE = "code",
  SPEC = "spec",
  GLOSSARY = "glossary",
  OTHER = "other",
}

export enum ExtractionStatus {
  PENDING = "pending",
  EXTRACTING = "extracting",
  EXTRACTED = "extracted",
  FAILED = "failed",
}

export enum SkillKind {
  CONTEXT = "context",
  AUTHORING = "authoring",
  ANALYZER = "analyzer",
  PROCEDURE = "procedure",
}

export enum SkillResourceLanguage {
  MARKDOWN = "markdown",
  SQL = "sql",
  YAML = "yaml",
  PYTHON = "python",
  PLAIN = "plain",
}

export enum CardType {
  TASK = "Task",
  STORY = "Story",
  BUG = "Bug",
  SPIKE = "Spike",
  DEMO = "Demo",
}

export enum Priority {
  LOW = "Low",
  MEDIUM = "Medium",
  HIGH = "High",
}

export enum CardStatus {
  DRAFT = "draft",
  READY = "ready",
  IN_PROGRESS = "in_progress",
  DONE = "done",
}

export enum CardDepRelation {
  DEPENDS_ON = "depends_on",
  PARALLEL_WITH = "parallel_with",
}

export enum CardInputKind {
  SKILL_RESOURCE = "skill_resource",
  ARTIFACT = "artifact",
  EXTERNAL = "external",
}

export enum TechChoiceRole {
  TARGET = "target",
  LEGACY = "legacy",
  OPTIONAL = "optional",
  MUST_AVOID = "must_avoid",
  TBD = "tbd",
}

export enum TechChoiceSource {
  CATALOG = "catalog",
  USER_ADDED = "user_added",
  LLM_SUGGESTED = "llm_suggested",
}

export enum LlmRunKind {
  PROPOSE_SKILL_SET = "propose_skill_set",
  DRAFT_SKILL_BODY = "draft_skill_body",
  PROPOSE_BACKLOG = "propose_backlog",
  DRAFT_CARD = "draft_card",
  SUGGEST_TECH = "suggest_tech",
  OTHER = "other",
}

export enum LlmRunStatus {
  SUCCESS = "success",
  PARSE_ERROR = "parse_error",
  PROVIDER_ERROR = "provider_error",
  IN_PROGRESS = "in_progress",
}

export enum ExportKind {
  FILESYSTEM = "filesystem",
  ZIP = "zip",
  JIRA_CSV = "jira_csv",
}

export enum UserRole {
  OWNER = "owner",
  MEMBER = "member",
  READONLY = "readonly",
}

// Base interfaces
export interface TenantView {
  id: string;
  name: string;
  created_at: string;
}

export interface UserView {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  created_at: string;
}

// Tech panorama
export interface TechItemView {
  id: string;
  dimension_id: string;
  slug: string;
  name: string;
  description?: string;
  tags: string[];
  is_custom: boolean;
}

export interface TechDimensionView {
  id: string;
  slug: string;
  name: string;
  description?: string;
  order_no: number;
  items: TechItemView[];
}

export interface TechChoiceView {
  id: string;
  project_id: string;
  dimension_id: string;
  dimension_slug: string;
  dimension_name: string;
  tech_item_id?: string;
  tech_item_slug?: string;
  tech_item_name?: string;
  role: TechChoiceRole;
  source: TechChoiceSource;
  accepted: boolean;
  llm_rationale?: string;
  llm_confidence?: number;
  notes?: string;
  order_no: number;
}

// Q&A Discovery
export interface QaAnswerView {
  project_id: string | null;
  question_key: string;
  prompt: string;
  required: boolean;
  placeholder: string;
  order: number;
  answer_md: string | null;
  updated_at: string | null;
  is_answered: boolean;
}

export interface QaStatsView {
  total_questions: number;
  answered_questions: number;
  completion_percentage: number;
  required_answered: number;
  required_total: number;
  required_percentage: number;
  questions_by_status: Record<string, number>;
}

export interface QaSummaryView {
  summary_md: string;
  completion_status: {
    overall: 'ready' | 'partial' | 'blocked';
    missing_keys: string[];
  };
}

export interface QaReadinessView {
  ready: boolean;
  readiness: 'ready' | 'partial' | 'blocked';
  message: string;
  missing_required: string[];
  recommended_next_steps: string[];
}

export interface QuestionMetadata {
  prompt: string;
  required: boolean;
  placeholder: string;
  order: number;
}

export interface ArtifactSummary {
  id: string;
  filename: string;
  kind: ArtifactKind;
  extraction_status: ExtractionStatus;
  size_bytes: number;
  content_md_excerpt?: string;
  content_md_truncated: boolean;
}

export interface ProjectView {
  id: string;
  tenant_id: string;
  owner_user_id: string;
  slug: string;
  name: string;
  objective: string;
  context_md?: string;
  card_code_prefix: string;
  card_template: CardTemplate;
  grouping: Grouping;
  status: ProjectStatus;
  project_type: ProjectType;
  source_technology?: string | null;
  target_technology?: string | null;
  llm_provider: LlmProvider;
  llm_model: string;
  llm_temperature: number;
  llm_enable_reasoning: boolean;
  created_at: string;
  updated_at: string;
}

// Skills
export interface SkillResourceView {
  id: string;
  skill_id: string;
  filename: string;
  content: string;
  language: SkillResourceLanguage;
  order_no: number;
}

export type SkillDraftStatus = 'none' | 'pending' | 'drafting' | 'success' | 'error';

export interface SkillView {
  id: string;
  project_id: string;
  slug: string;
  name: string;
  description: string;
  kind: SkillKind;
  body_md: string;
  order_no: number;
  resources: SkillResourceView[];
  // Draft status tracking
  draft_status: SkillDraftStatus;
  last_llm_run_id?: string | null;
  draft_error?: string | null;
}

// Cards and phases
export interface CardInputView {
  id: string;
  card_id: string;
  kind: CardInputKind;
  path: string;
  label?: string;
  order_no: number;
}

export interface CardDepView {
  from_code: string;
  to_code: string;
  relation: CardDepRelation;
}

export interface CardView {
  id: string;
  phase_id: string;
  code: string;
  title: string;
  type: CardType;
  story_points?: number;
  priority?: Priority;
  status: CardStatus;
  human_gate: boolean;
  human_gate_checklist_md?: string;
  context_md?: string;
  task_md?: string;
  outputs_md?: string;
  acceptance_criteria_md?: string;
  order_no: number;
  skill_slugs: string[];
  depends_on_codes: string[];
  parallel_with_codes: string[];
  inputs: CardInputView[];
  created_at: string;
  updated_at: string;
}

export interface PhaseView {
  id: string;
  project_id: string;
  code: string;
  name: string;
  description_md?: string;
  order_no: number;
  cards: CardView[];
}

// Project context
export interface ProjectContext {
  objective: string;
  qa: Record<string, string>;
  tech_choices_by_dimension: Record<string, TechChoiceView[]>;
  artifact_summaries: ArtifactSummary[];
  context_notes_md: string;
}

// LLM runs
export interface LlmRunView {
  id: string;
  project_id?: string;
  kind: LlmRunKind;
  provider: LlmProvider;
  model: string;
  response_text?: string;
  response_json?: Record<string, any>;
  reasoning_md?: string;
  reasoning_tokens?: number;
  reasoning_truncated: boolean;
  extended_thinking_enabled: boolean;
  tokens_in?: number;
  tokens_out?: number;
  cost_usd?: number;
  status: LlmRunStatus;
  error?: string;
  created_at: string;
}

// Exports
export interface ExportView {
  id: string;
  project_id: string;
  kind: ExportKind;
  target_path?: string;
  manifest_json: Record<string, any>;
  created_at: string;
}

// API Request/Response types
export interface CreateProjectRequest {
  slug: string;
  name: string;
  objective: string;
  card_code_prefix?: string;
  context_md?: string;
  project_type?: ProjectType;
  card_template?: CardTemplate;
  source_technology?: string;
  target_technology?: string;
  llm_provider?: LlmProvider;
  llm_model?: string;
}

export interface UpdateProjectRequest {
  name?: string;
  objective?: string;
  context_md?: string;
  llm_provider?: LlmProvider;
  llm_model?: string;
  llm_temperature?: number;
}

export interface SetQaAnswerRequest {
  answer_md: string;
}

export interface SetTechChoiceRequest {
  role: TechChoiceRole;
  notes?: string;
}

export interface ProposeSkillsetRequest {
  // Empty - uses project context
}

export interface DraftSkillRequest {
  skill_id: string;
}

export interface ProposeBacklogRequest {
  // Empty - uses project context
}

export interface DraftCardRequest {
  phase_code: string;
  card_type: CardType;
  initial_title: string;
}

export interface SuggestTechRequest {
  dimension_slug: string;
}

export interface ValidationReport {
  project_slug: string;
  overall_status: 'pass' | 'warn' | 'fail';
  validators: Array<{
    name: string;
    status: 'pass' | 'warn' | 'fail';
    issues: Array<{
      severity: 'info' | 'warning' | 'error';
      message: string;
      path?: string;
    }>;
  }>;
}

// API Response wrappers
export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface ApiError {
  detail: string;
  code?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
}

// Skill Proposal Types
export interface ProposedSkill {
  slug: string;
  name: string;
  description: string;
  kind: SkillKind;
  rationale: string;
  sibling_refs: string[];
}

export interface ProposeSkillsResponse {
  skills: ProposedSkill[];
  coverage_notes: string;
  gaps: string[];
  llm_run_id: string;
}

export interface CreateSkillRequest {
  slug: string;
  name: string;
  description: string;
  kind: SkillKind;
  body_md?: string;
  order_no?: number;
}

export interface UpdateSkillRequest {
  name?: string;
  description?: string;
  kind?: SkillKind;
  body_md?: string;
  order_no?: number;
}

export interface BulkCreateSkillRequest {
  slug: string;
  name: string;
  description: string;
  kind: SkillKind;
  rationale?: string;
  body_md?: string;
}

export interface BulkCreateSkillsRequest {
  skills: BulkCreateSkillRequest[];
}

export interface BulkCreateSkillsResponse {
  created: number;
  skills: SkillView[];
}

export interface SkillStatsResponse {
  total_skills: number;
  by_kind: Record<string, number>;
  with_content: number;
  with_resources: number;
  completion_percentage: number;
  by_draft_status: Record<SkillDraftStatus, number>;
}

// Draft skill body request/response
export interface DraftSkillBodyRequest {
  include_resources?: boolean;
}

export interface DraftSkillBodyResponse {
  body_md: string;
  resources_created: number;
  sibling_skills_referenced: string[];
  llm_run_id: string;
}

// Draft all skills request/response
export interface DraftAllSkillsRequest {
  include_resources?: boolean;
  force?: boolean;
}

export interface DraftAllSkillsResponse {
  queued: number;
  skill_slugs: string[];
}

// Resource CRUD
export interface CreateResourceRequest {
  filename: string;
  content: string;
  language?: SkillResourceLanguage;
  order_no?: number;
}

export interface UpdateResourceRequest {
  filename?: string;
  content?: string;
  language?: SkillResourceLanguage;
  order_no?: number;
}

// Backlog proposal response
export interface ProposeBacklogResponse {
  phases: PhaseView[];
  rationale_md: string;
  critical_path_codes: string[];
  llm_run_id: string;
}

// Cards stats response
export interface CardsStatsResponse {
  total: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
  total_story_points: number;
}

// Card section update
export interface UpdateSectionRequest {
  content: string;
}

export interface RegenerateSectionResponse {
  section: string;
  content: string;
  llm_run_id: string;
}

export interface DraftCardResponse {
  card: CardView;
  llm_run_id: string;
}

// Card dependencies update
export interface UpdateDependenciesRequest {
  depends_on_codes: string[];
  parallel_with_codes: string[];
}

// Card input CRUD
export interface CreateCardInputRequest {
  kind: CardInputKind;
  path: string;
  label?: string;
  order_no?: number;
}

export interface UpdateCardInputRequest {
  kind?: CardInputKind;
  path?: string;
  label?: string;
  order_no?: number;
}

// DAG View
export interface DagNodeView {
  id: string;
  code: string;
  title: string;
  type: CardType;
  status: CardStatus;
  phase_code: string;
  phase_name: string;
  story_points?: number;
}

export interface DagEdgeView {
  id: string;
  source: string;
  target: string;
  relation: CardDepRelation;
}

export interface DagResponse {
  nodes: DagNodeView[];
  edges: DagEdgeView[];
}

// Export / Validation
export interface ValidationIssueView {
  severity: 'error' | 'warning';
  code: string;
  message: string;
  location?: Record<string, string>;
}

export interface ValidationResponse {
  valid: boolean;
  error_count: number;
  warning_count: number;
  issues: ValidationIssueView[];
}

export interface ExportTreeNode {
  name: string;
  type: 'file' | 'directory';
  size?: number;
  children?: ExportTreeNode[];
}

export interface ExportPreviewResponse {
  tree: ExportTreeNode[];
  total_files: number;
  total_size_bytes: number;
}

// Worker Status
export type WorkerStatusType = 'healthy' | 'no_workers' | 'redis_down';

export interface WorkerStatusResponse {
  redis_connected: boolean;
  pending_jobs: number;
  workers_detected: number;
  status: WorkerStatusType;
  error: string | null;
}

// =============================================================================
// Migration Map Types
// =============================================================================

export enum MapObjectType {
  TABLE = 'table',
  FILE = 'file',
  API = 'api',
  QUEUE = 'queue',
  TOPIC = 'topic',
}

export enum MapObjectDirection {
  READ = 'read',
  WRITE = 'write',
  LOOKUP = 'lookup',
}

export enum FlowRelationshipType {
  DATA_FLOW = 'data_flow',
  CONTROL = 'control',
  INFERRED = 'inferred',
}

export interface MapNode {
  id: string;
  type: string;
  data: Record<string, unknown>;
  position?: { x: number; y: number };
}

export interface MapEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  animated?: boolean;
  style?: Record<string, unknown>;
}

export interface MapStats {
  total_packages: number;
  analyzed_packages: number;
  total_objects: number;
  total_dependencies: number;
  cluster_count: number;
  orphan_count: number;
  cycles_detected: number;
  suggested_waves: number;
}

export interface ClusterView {
  id: string;
  project_id: string;
  name?: string;
  package_count: number;
  total_blockers: number;
  suggested_wave?: number;
  created_at: string;
}

export interface MapVisualization {
  nodes: MapNode[];
  edges: MapEdge[];
  clusters: ClusterView[];
  orphan_packages: string[];
  stats: MapStats;
}

export interface MigrationObjectView {
  id: string;
  project_id: string;
  object_type: MapObjectType;
  object_name: string;
  connection_ref?: string;
  schema_name?: string;
  database_name?: string;
  read_by_count: number;
  written_by_count: number;
  first_seen_at: string;
}

export interface ObjectWithPackages extends MigrationObjectView {
  reading_packages: string[];
  writing_packages: string[];
}

export interface FlowDepView {
  id: string;
  project_id: string;
  upstream_package_id: string;
  upstream_package_name: string;
  downstream_package_id: string;
  downstream_package_name: string;
  via_object_id?: string;
  via_object_name?: string;
  relationship_type: FlowRelationshipType;
  is_confirmed: boolean;
  is_rejected: boolean;
  created_at: string;
}

export interface WaveSuggestion {
  package_id: string;
  package_name: string;
  current_wave?: number;
  suggested_wave: number;
  reason: string;
}

export interface WaveSuggestionsResult {
  suggestions: WaveSuggestion[];
  total_waves: number;
  unassignable: string[];
}

export interface ClusterWithMembers extends ClusterView {
  members: Array<{
    package_id: string;
    package_name: string;
    cluster_role: 'source' | 'sink' | 'internal';
  }>;
}

export interface MapRefreshResult {
  objects_created: number;
  objects_updated: number;
  dependencies_created: number;
  dependencies_removed: number;
  clusters_created: number;
  clusters_merged: number;
  cycles_detected: number;
  duration_ms: number;
}

// =============================================================================
// Propagation Types
// =============================================================================

export enum PropagationScope {
  PROJECT = 'project',
  CLUSTER = 'cluster',
  DOMAIN = 'domain',
  SIMILAR = 'similar',
}

export interface PropagationPreview {
  decision_id: string;
  decision_type: string;
  question: string;
  resolution: string;
  scope: PropagationScope;
  would_affect_count: number;
  already_resolved_count: number;
  affected_packages: Array<{
    id: string;
    name: string;
    domain?: string;
    status: string;
  }>;
}

export interface PropagationResult {
  source_decision_id: string;
  decision_type: string;
  packages_affected: number;
  packages_already_resolved: number;
  affected_package_ids: string[];
  errors: string[];
  propagated_at: string;
}

export interface PropagationRequest {
  decision_id: string;
  scope?: PropagationScope;
  cluster_id?: string;
  domain?: string;
  dry_run?: boolean;
}

export interface BatchWaveAssignment {
  assignments: Array<{ package_id: string; wave: number }>;
}

export interface BatchWaveResult {
  successful: number;
  failed: number;
  errors: string[];
  assigned_packages: string[];
}

// Generation types (Phase 6)
export enum GenerationStrategy {
  SQL_NOTEBOOK = "sql",
  PYSPARK = "pyspark",
  HYBRID_SINGLE = "hybrid",
  MODULAR = "modular",
}

export enum ArtifactTier {
  ORCHESTRATOR = "orchestrator",
  SQL_MODULE = "sql_module",
  PYSPARK_MODULE = "pyspark_module",
  HYBRID_MODULE = "hybrid_module",
  CONFIG = "config",
  DOCUMENTATION = "documentation",
  TEST = "test",
}

export interface GeneratedArtifact {
  name: string;
  relative_path: string;
  tier: ArtifactTier;
  language: string;
  content: string;
  line_count: number;
  depends_on: string[];
  notes: string[];
}

export interface GenerationOptions {
  force_strategy?: GenerationStrategy;
  target_catalog?: string;
  target_schema?: string;
  include_comments?: boolean;
  include_docstring_header?: boolean;
  include_validation_cells?: boolean;
  enable_photon_hints?: boolean;
  use_delta_merge?: boolean;
}

export interface GenerationPreview {
  package_id: string;
  package_name: string;
  strategy: GenerationStrategy;
  rationale: string;
  planned_artifacts: Array<{
    name: string;
    tier: string;
    purpose: string;
    estimated_cells?: number;
  }>;
}

export interface GenerationResult {
  package_id: string;
  package_name: string;
  strategy: GenerationStrategy;
  strategy_source: string;
  artifacts: GeneratedArtifact[];
  total_files: number;
  total_lines: number;
  status: string;
  warnings: string[];
  errors: string[];
  generated_at: string;
}

// Design Guidance types (Phase 7)
export enum DataPatternCategory {
  LOAD = "load",
  SCD = "scd",
  DELETE = "delete",
  INCREMENTAL = "incremental",
  TRANSFORM = "transform",
  UNKNOWN = "unknown",
}

export enum DataPattern {
  MERGE = "merge",
  DELETE_INSERT = "delete_insert",
  APPEND_ONLY = "append_only",
  UPDATE_IN_PLACE = "update_in_place",
  SCD_TYPE_1 = "scd_type_1",
  SCD_TYPE_2 = "scd_type_2",
  SCD_TYPE_3 = "scd_type_3",
  SOFT_DELETE = "soft_delete",
  HARD_DELETE = "hard_delete",
  WATERMARK = "watermark",
  CDC = "cdc",
  DELTA_DIFF = "delta_diff",
  LOOKUP_ENRICH = "lookup_enrich",
  AGGREGATE = "aggregate",
  PIVOT_UNPIVOT = "pivot_unpivot",
  UNKNOWN = "unknown",
}

export enum MedallionLayer {
  BRONZE = "bronze",
  SILVER = "silver",
  GOLD = "gold",
  NOT_APPLICABLE = "n/a",
}

export interface TaskPatternResult {
  task_name: string;
  pattern: DataPattern;
  pattern_name: string;
  category: DataPatternCategory;
  layer: MedallionLayer;
  target_table: string | null;
  confidence: number;
  detection_evidence: string[];
}

export interface PackageDesignAnalysis {
  package_name: string;
  task_patterns: TaskPatternResult[];
  pattern_summary: Record<string, number>;
  layer_summary: Record<string, number>;
  photon_eligible: boolean;
  performance_notes: string[];
}

// Skills types (Phase 7)
export interface SkillSummary {
  id: string;
  name: string;
  description: string;
  has_resources: boolean;
  capabilities: string[];
}

export interface SkillDetail extends SkillSummary {
  content: string;
  path: string;
  when_to_use: string;
}

// =============================================================================
// Gaps
// =============================================================================

export type GapStatus =
  | "open"
  | "addressed_by_skill"
  | "covered_by_mcp"
  | "out_of_scope";

export type GapSource = "propose_skill_set" | "manual";

export interface GapView {
  id: string;
  project_id: string;
  title: string;
  source: GapSource;
  status: GapStatus;
  addressed_by_skill_id: string | null;
  covered_by_mcp_key: string | null;
  decision_rationale: string | null;
  decided_by_user_id: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface GapsStatsResponse {
  open: number;
  addressed_by_skill: number;
  covered_by_mcp: number;
  out_of_scope: number;
  total: number;
}

export interface CreateGapRequest {
  title: string;
}

export interface AddressBySkillRequest {
  skill_slug: string;
  rationale?: string;
}

export interface CoverByMcpRequest {
  mcp_key: string;
  rationale?: string;
}

export interface OutOfScopeRequest {
  rationale?: string;
}

// =============================================================================
// MCP Catalog
// =============================================================================

export type MCPCategory =
  | "source_control"
  | "database"
  | "project_management"
  | "documentation"
  | "messaging"
  | "monitoring"
  | "utility"
  | "cloud";

export type MCPRiskLevel = "N1" | "N2" | "N3";

export interface MCPCatalogListItem {
  key: string;
  name: string;
  description: string;
  vendor: string;
  category: MCPCategory;
  requires_approval: boolean;
  has_secrets: boolean;
  tool_count: number;
}

export interface MCPCatalogEnvVar {
  required: boolean;
  secret: boolean;
  label: string;
  hint: string;
}

export interface MCPCatalogConfigField {
  type: "string" | "number" | "boolean" | "url";
  required: boolean;
  label: string;
  hint: string;
  default: string | null;
}

export interface MCPCatalogTool {
  name: string;
  description: string;
  risk_level: MCPRiskLevel;
}

export interface MCPCatalogEntry {
  key: string;
  name: string;
  description: string;
  vendor: string;
  category: MCPCategory;

  // Counts
  env_var_count: number;
  secret_count: number;
  config_field_count: number;
  tool_count: number;

  // Flags
  has_secrets: boolean;
  has_n3_tools: boolean;
  requires_approval: boolean;

  documentation_url: string | null;
  icon: string | null;

  // Detail (used by configuration form)
  run_command: string;
  env_vars: Record<string, MCPCatalogEnvVar>;
  config_fields: Record<string, MCPCatalogConfigField>;
  tools: MCPCatalogTool[];
}

// =============================================================================
// MCP Configuration (per-project)
// =============================================================================

export interface MCPConfigSummary {
  id: string;
  mcp_key: string;
  mcp_name: string;
  mcp_category: MCPCategory;
  enabled: boolean;
  validated_at: string | null;
  has_validation_error: boolean;
}

export interface MCPConfigView {
  id: string;
  project_id: string;
  mcp_key: string;
  env_vars_masked: Record<string, string>;
  config_fields: Record<string, string | number | boolean>;
  enabled: boolean;
  validated_at: string | null;
  validation_error: string | null;
  mcp_name: string;
  mcp_description: string;
  mcp_category: MCPCategory;
  mcp_vendor: string;
  created_at: string;
  updated_at: string;
  created_by: string | null;
}

export interface MCPConfigCreate {
  mcp_key: string;
  env_vars: Record<string, string>;
  config_fields: Record<string, string | number | boolean>;
  enabled?: boolean;
  created_by?: string;
}

export interface MCPConfigUpdate {
  env_vars?: Record<string, string>;
  config_fields?: Record<string, string | number | boolean>;
  enabled?: boolean;
}

export interface MCPConfigToggle {
  enabled: boolean;
}

export interface MCPConfigValidation {
  valid: boolean;
  missing_env_vars: string[];
  missing_config_fields: string[];
  errors: string[];
}

export interface MCPExportPreview {
  server_count: number;
  servers: string[];
  has_secrets: boolean;
  warning: string;
}

export interface CursorMCPServerConfig {
  command: string;
  args: string[];
  env: Record<string, string>;
}

export interface CursorMCPConfig {
  mcpServers: Record<string, CursorMCPServerConfig>;
}