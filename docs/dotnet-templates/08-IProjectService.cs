// =============================================================================
// IProjectService.cs - Service Interfaces
// =============================================================================
// Location: AgentsWorkshop.Core/Interfaces/
// =============================================================================

using AgentsWorkshop.Contracts;
using AgentsWorkshop.Contracts.Requests;
using AgentsWorkshop.Contracts.Responses;
using AgentsWorkshop.Domain.Entities;
using AgentsWorkshop.Domain.Enums;

namespace AgentsWorkshop.Core.Interfaces;

// =============================================================================
// Project Service Interface
// =============================================================================

public interface IProjectService
{
    Task<ProjectResponse> CreateAsync(Guid tenantId, CreateProjectRequest request, CancellationToken cancellationToken = default);
    
    Task<ProjectDetailResponse?> GetByIdAsync(Guid id, CancellationToken cancellationToken = default);
    
    Task<ProjectResponse?> GetBySlugAsync(string slug, CancellationToken cancellationToken = default);
    
    Task<PaginatedResponse<ProjectResponse>> GetPagedAsync(
        Guid tenantId,
        int page = 1,
        int pageSize = 20,
        ProjectStatus? status = null,
        CancellationToken cancellationToken = default);
    
    Task<ProjectResponse?> UpdateAsync(Guid id, UpdateProjectRequest request, CancellationToken cancellationToken = default);
    
    Task<bool> DeleteAsync(Guid id, CancellationToken cancellationToken = default);
    
    Task<ProjectDetailResponse?> UpdateQaAnswersAsync(
        Guid projectId,
        IReadOnlyList<ProjectQaAnswerRequest> answers,
        CancellationToken cancellationToken = default);
}

// =============================================================================
// Skill Service Interface
// =============================================================================

public interface ISkillService
{
    Task<SkillDetailResponse> CreateAsync(Guid projectId, CreateSkillRequest request, CancellationToken cancellationToken = default);
    
    Task<SkillDetailResponse?> GetByIdAsync(Guid id, CancellationToken cancellationToken = default);
    
    Task<SkillDetailResponse?> GetBySlugAsync(Guid projectId, string slug, CancellationToken cancellationToken = default);
    
    Task<IReadOnlyList<SkillSummaryResponse>> GetByProjectAsync(Guid projectId, CancellationToken cancellationToken = default);
    
    Task<SkillDetailResponse?> UpdateAsync(Guid id, UpdateSkillRequest request, CancellationToken cancellationToken = default);
    
    Task<bool> DeleteAsync(Guid id, CancellationToken cancellationToken = default);
    
    Task<SkillDetailResponse?> AddResourceAsync(Guid skillId, SkillResourceRequest resource, CancellationToken cancellationToken = default);
    
    Task<bool> RemoveResourceAsync(Guid skillId, Guid resourceId, CancellationToken cancellationToken = default);
}

// =============================================================================
// Backlog Service Interface
// =============================================================================

public interface IBacklogService
{
    // Phase Operations
    Task<PhaseDetailResponse> CreatePhaseAsync(Guid projectId, CreatePhaseRequest request, CancellationToken cancellationToken = default);
    
    Task<IReadOnlyList<PhaseDetailResponse>> GetPhasesByProjectAsync(Guid projectId, CancellationToken cancellationToken = default);
    
    Task<PhaseDetailResponse?> UpdatePhaseAsync(Guid phaseId, CreatePhaseRequest request, CancellationToken cancellationToken = default);
    
    Task<bool> DeletePhaseAsync(Guid phaseId, CancellationToken cancellationToken = default);
    
    Task<bool> ReorderPhasesAsync(Guid projectId, IReadOnlyList<Guid> phaseIds, CancellationToken cancellationToken = default);

    // Card Operations
    Task<CardDetailResponse> CreateCardAsync(Guid phaseId, CreateCardRequest request, CancellationToken cancellationToken = default);
    
    Task<CardDetailResponse?> GetCardByIdAsync(Guid id, CancellationToken cancellationToken = default);
    
    Task<CardDetailResponse?> GetCardByCodeAsync(Guid projectId, string code, CancellationToken cancellationToken = default);
    
    Task<IReadOnlyList<CardSummaryResponse>> GetCardsByPhaseAsync(Guid phaseId, CancellationToken cancellationToken = default);
    
    Task<CardDetailResponse?> UpdateCardAsync(Guid cardId, UpdateCardRequest request, CancellationToken cancellationToken = default);
    
    Task<bool> DeleteCardAsync(Guid cardId, CancellationToken cancellationToken = default);
    
    Task<bool> MoveCardToPhaseAsync(Guid cardId, Guid newPhaseId, CancellationToken cancellationToken = default);

    // DAG Operations
    Task<DagGraphResponse> GetDagAsync(Guid projectId, CancellationToken cancellationToken = default);
}

// =============================================================================
// Validation Service Interface
// =============================================================================

public interface IValidationService
{
    Task<ValidationResultResponse> ValidateProjectAsync(Guid projectId, CancellationToken cancellationToken = default);
    
    Task<ValidationResultResponse> ValidateSkillAsync(Guid skillId, CancellationToken cancellationToken = default);
    
    Task<ValidationResultResponse> ValidateCardAsync(Guid cardId, CancellationToken cancellationToken = default);
    
    Task<ValidationResultResponse> ValidateDagAsync(Guid projectId, CancellationToken cancellationToken = default);
    
    Task<bool> HasCyclicDependenciesAsync(Guid projectId, CancellationToken cancellationToken = default);
}

// =============================================================================
// Export Service Interface
// =============================================================================

public interface IExportService
{
    Task<ExportResultResponse> ExportProjectAsync(
        Guid projectId,
        ExportRequest request,
        CancellationToken cancellationToken = default);
    
    Task<byte[]> ExportToZipAsync(Guid projectId, CancellationToken cancellationToken = default);
    
    Task<IReadOnlyList<ExportResultResponse>> GetExportHistoryAsync(
        Guid projectId,
        CancellationToken cancellationToken = default);
}

// =============================================================================
// LLM Service Interface
// =============================================================================

public interface ILlmService
{
    Task<string> GenerateAsync(
        string promptName,
        Dictionary<string, object> context,
        Guid? projectId = null,
        CancellationToken cancellationToken = default);
    
    Task<T> GenerateStructuredAsync<T>(
        string promptName,
        Dictionary<string, object> context,
        Guid? projectId = null,
        CancellationToken cancellationToken = default) where T : class;
    
    Task<IReadOnlyList<LlmRunResponse>> GetRunHistoryAsync(
        Guid? projectId = null,
        int limit = 50,
        CancellationToken cancellationToken = default);
}

// =============================================================================
// Artifact Service Interface
// =============================================================================

public interface IArtifactService
{
    Task<Guid> UploadAsync(
        Guid projectId,
        string fileName,
        Stream content,
        CancellationToken cancellationToken = default);
    
    Task<string?> GetExtractedTextAsync(Guid artifactId, CancellationToken cancellationToken = default);
    
    Task<bool> DeleteAsync(Guid artifactId, CancellationToken cancellationToken = default);
    
    Task TriggerExtractionAsync(Guid artifactId, CancellationToken cancellationToken = default);
}
