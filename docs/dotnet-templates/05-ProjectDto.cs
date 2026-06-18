// =============================================================================
// DTOs - Request and Response Data Transfer Objects
// =============================================================================
// Location: AgentsWorkshop.Contracts/
// Mirrors: Python Pydantic schemas (views.py, llm_io.py)
// =============================================================================

using System.ComponentModel.DataAnnotations;
using System.Text.Json.Serialization;
using AgentsWorkshop.Domain.Enums;

namespace AgentsWorkshop.Contracts;

// =============================================================================
// Common DTOs
// =============================================================================

/// <summary>
/// Paginated response wrapper.
/// </summary>
public record PaginatedResponse<T>(
    IReadOnlyList<T> Items,
    int Total,
    int Page,
    int PageSize,
    int TotalPages
);

/// <summary>
/// Validation error details.
/// </summary>
public record ValidationErrorDto(
    string Field,
    string Message,
    ValidationSeverity Severity
);

/// <summary>
/// Generic API response wrapper.
/// </summary>
public record ApiResponse<T>(
    bool Success,
    T? Data,
    string? Message = null,
    IReadOnlyList<ValidationErrorDto>? Errors = null
);

// =============================================================================
// Project DTOs
// =============================================================================

namespace AgentsWorkshop.Contracts.Requests;

public record CreateProjectRequest(
    [Required][MaxLength(200)] string Name,
    [MaxLength(2000)] string? Objective = null
);

public record UpdateProjectRequest(
    [MaxLength(200)] string? Name = null,
    [MaxLength(2000)] string? Objective = null,
    ProjectStatus? Status = null,
    LlmProvider? LlmProvider = null,
    [MaxLength(50)] string? LlmModel = null,
    [Range(0.0, 2.0)] decimal? LlmTemperature = null
);

public record ProjectQaAnswerRequest(
    [Required] string QuestionKey,
    string? Answer
);

namespace AgentsWorkshop.Contracts.Responses;

public record ProjectResponse(
    Guid Id,
    string Name,
    string Slug,
    string? Objective,
    ProjectStatus Status,
    string? CardCodePrefix,
    int SkillCount,
    int CardCount,
    DateTime CreatedAt,
    DateTime UpdatedAt
);

public record ProjectDetailResponse(
    Guid Id,
    string Name,
    string Slug,
    string? Objective,
    ProjectStatus Status,
    string? CardCodePrefix,
    LlmProvider? LlmProvider,
    string? LlmModel,
    decimal? LlmTemperature,
    IReadOnlyList<ProjectQaAnswerResponse> QaAnswers,
    IReadOnlyList<ProjectTechChoiceResponse> TechChoices,
    IReadOnlyList<SkillSummaryResponse> Skills,
    IReadOnlyList<PhaseSummaryResponse> Phases,
    DateTime CreatedAt,
    DateTime UpdatedAt
);

public record ProjectQaAnswerResponse(
    string QuestionKey,
    string? Answer,
    bool IsRequired
);

public record ProjectTechChoiceResponse(
    Guid TechItemId,
    string DimensionCode,
    string ItemCode,
    string ItemName,
    string? Notes
);

// =============================================================================
// Skill DTOs
// =============================================================================

namespace AgentsWorkshop.Contracts.Requests;

public record CreateSkillRequest(
    [Required][MaxLength(100)] string Slug,
    [Required][MaxLength(200)] string Name,
    [MaxLength(2000)] string? Description,
    [Required] SkillKind Kind,
    string? Body,
    IReadOnlyList<SkillResourceRequest>? Resources = null
);

public record UpdateSkillRequest(
    [MaxLength(200)] string? Name = null,
    [MaxLength(2000)] string? Description = null,
    SkillKind? Kind = null,
    string? Body = null
);

public record SkillResourceRequest(
    [Required][MaxLength(255)] string Filename,
    ResourceLanguage Language,
    [Required] string Content
);

namespace AgentsWorkshop.Contracts.Responses;

public record SkillSummaryResponse(
    Guid Id,
    string Slug,
    string Name,
    SkillKind Kind,
    int ResourceCount
);

public record SkillDetailResponse(
    Guid Id,
    string Slug,
    string Name,
    string? Description,
    SkillKind Kind,
    string? Body,
    IReadOnlyList<SkillResourceResponse> Resources,
    IReadOnlyList<CardReferenceResponse> UsedByCards,
    DateTime CreatedAt,
    DateTime UpdatedAt
);

public record SkillResourceResponse(
    Guid Id,
    string Filename,
    ResourceLanguage Language,
    string Content
);

// =============================================================================
// Backlog DTOs (Phase & Card)
// =============================================================================

namespace AgentsWorkshop.Contracts.Requests;

public record CreatePhaseRequest(
    [Required][MaxLength(100)] string Code,
    [Required][MaxLength(200)] string Title,
    [MaxLength(2000)] string? Description = null,
    int? Order = null
);

public record CreateCardRequest(
    [Required][MaxLength(20)] string Code,
    [Required][MaxLength(300)] string Title,
    CardType Type = CardType.Task,
    [Range(1, 21)] int? StoryPoints = null,
    string? ContextMd = null,
    string? TaskMd = null,
    string? OutputsMd = null,
    string? AcceptanceCriteriaMd = null,
    bool HumanGate = false,
    string? HumanGateChecklistMd = null,
    bool CanRunParallel = false,
    [Required] IReadOnlyList<string> SkillSlugs = null!,
    IReadOnlyList<string>? DependsOnCodes = null,
    IReadOnlyList<CardInputRequest>? Inputs = null
);

public record UpdateCardRequest(
    [MaxLength(300)] string? Title = null,
    CardType? Type = null,
    CardStatus? Status = null,
    [Range(1, 21)] int? StoryPoints = null,
    string? ContextMd = null,
    string? TaskMd = null,
    string? OutputsMd = null,
    string? AcceptanceCriteriaMd = null,
    bool? HumanGate = null,
    string? HumanGateChecklistMd = null,
    bool? CanRunParallel = null,
    IReadOnlyList<string>? SkillSlugs = null,
    IReadOnlyList<string>? DependsOnCodes = null
);

public record CardInputRequest(
    [Required] string Kind,
    string? Path = null,
    string? Description = null
);

namespace AgentsWorkshop.Contracts.Responses;

public record PhaseSummaryResponse(
    Guid Id,
    string Code,
    string Title,
    int Order,
    int CardCount
);

public record PhaseDetailResponse(
    Guid Id,
    string Code,
    string Title,
    string? Description,
    int Order,
    IReadOnlyList<CardSummaryResponse> Cards
);

public record CardSummaryResponse(
    Guid Id,
    string Code,
    string Title,
    CardType Type,
    CardStatus Status,
    int? StoryPoints,
    bool HumanGate,
    int SkillCount,
    int DependencyCount
);

public record CardDetailResponse(
    Guid Id,
    string Code,
    string Title,
    CardType Type,
    CardStatus Status,
    int? StoryPoints,
    string? ContextMd,
    string? TaskMd,
    string? OutputsMd,
    string? AcceptanceCriteriaMd,
    bool HumanGate,
    string? HumanGateChecklistMd,
    bool CanRunParallel,
    PhaseSummaryResponse Phase,
    IReadOnlyList<SkillSummaryResponse> Skills,
    IReadOnlyList<CardReferenceResponse> Dependencies,
    IReadOnlyList<CardInputResponse> Inputs,
    DateTime CreatedAt,
    DateTime UpdatedAt
);

public record CardReferenceResponse(
    Guid Id,
    string Code,
    string Title
);

public record CardInputResponse(
    Guid Id,
    string Kind,
    string? Path,
    string? Description
);

// =============================================================================
// Validation DTOs
// =============================================================================

namespace AgentsWorkshop.Contracts.Responses;

public record ValidationResultResponse(
    bool IsValid,
    int ErrorCount,
    int WarningCount,
    IReadOnlyList<ValidationIssueResponse> Issues
);

public record ValidationIssueResponse(
    ValidationSeverity Severity,
    string Code,
    string Message,
    string? EntityType,
    string? EntityId,
    string? Field
);

// =============================================================================
// Export DTOs
// =============================================================================

namespace AgentsWorkshop.Contracts.Requests;

public record ExportRequest(
    string Format = "filesystem",
    string? OutputPath = null
);

namespace AgentsWorkshop.Contracts.Responses;

public record ExportResultResponse(
    Guid ExportId,
    string Format,
    int TotalSkills,
    int TotalCards,
    int Warnings,
    IReadOnlyList<string> GeneratedFiles,
    DateTime ExportedAt
);

// =============================================================================
// LLM DTOs
// =============================================================================

namespace AgentsWorkshop.Contracts.Requests;

public record LlmGenerateRequest(
    [Required] string PromptName,
    Dictionary<string, object>? Context = null
);

namespace AgentsWorkshop.Contracts.Responses;

public record LlmRunResponse(
    Guid Id,
    string PromptName,
    LlmProvider Provider,
    string Model,
    int InputTokens,
    int OutputTokens,
    decimal? CostUsd,
    TimeSpan? Duration,
    DateTime CreatedAt
);

// =============================================================================
// DAG Visualization DTOs
// =============================================================================

namespace AgentsWorkshop.Contracts.Responses;

public record DagNode(
    string Id,
    string Code,
    string Title,
    string Phase,
    CardStatus Status,
    bool HumanGate
);

public record DagEdge(
    string Source,
    string Target
);

public record DagGraphResponse(
    IReadOnlyList<DagNode> Nodes,
    IReadOnlyList<DagEdge> Edges
);
