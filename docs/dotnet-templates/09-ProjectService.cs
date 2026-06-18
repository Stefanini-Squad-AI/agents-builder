// =============================================================================
// ProjectService.cs - Service Implementation
// =============================================================================
// Location: AgentsWorkshop.Core/Services/ProjectService.cs
// =============================================================================

using Microsoft.Extensions.Logging;
using AgentsWorkshop.Contracts;
using AgentsWorkshop.Contracts.Requests;
using AgentsWorkshop.Contracts.Responses;
using AgentsWorkshop.Core.Interfaces;
using AgentsWorkshop.Domain.Entities;
using AgentsWorkshop.Domain.Enums;

namespace AgentsWorkshop.Core.Services;

public class ProjectService : IProjectService
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<ProjectService> _logger;

    public ProjectService(IUnitOfWork unitOfWork, ILogger<ProjectService> logger)
    {
        _unitOfWork = unitOfWork;
        _logger = logger;
    }

    // =============================================================================
    // Create Project
    // =============================================================================

    public async Task<ProjectResponse> CreateAsync(
        Guid tenantId,
        CreateProjectRequest request,
        CancellationToken cancellationToken = default)
    {
        // Generate slug from name
        var slug = GenerateSlug(request.Name);
        
        // Ensure unique slug
        var baseSlug = slug;
        var counter = 1;
        while (await _unitOfWork.Projects.SlugExistsAsync(slug, null, cancellationToken))
        {
            slug = $"{baseSlug}-{counter++}";
        }

        // Generate card code prefix (2-8 uppercase chars from slug)
        var cardCodePrefix = GenerateCardCodePrefix(slug);

        var project = new Project
        {
            Name = request.Name,
            Slug = slug,
            Objective = request.Objective,
            Status = ProjectStatus.Draft,
            CardCodePrefix = cardCodePrefix,
            TenantId = tenantId
        };

        _unitOfWork.Projects.Add(project);
        await _unitOfWork.SaveChangesAsync(cancellationToken);

        _logger.LogInformation("Created project {ProjectId} with slug {Slug}", project.Id, project.Slug);

        return MapToResponse(project);
    }

    // =============================================================================
    // Get Project by ID
    // =============================================================================

    public async Task<ProjectDetailResponse?> GetByIdAsync(Guid id, CancellationToken cancellationToken = default)
    {
        var project = await _unitOfWork.Projects.GetWithFullDetailsAsync(id, cancellationToken);
        
        if (project == null)
            return null;

        return MapToDetailResponse(project);
    }

    // =============================================================================
    // Get Project by Slug
    // =============================================================================

    public async Task<ProjectResponse?> GetBySlugAsync(string slug, CancellationToken cancellationToken = default)
    {
        var project = await _unitOfWork.Projects.GetBySlugAsync(slug, cancellationToken);
        
        return project != null ? MapToResponse(project) : null;
    }

    // =============================================================================
    // Get Paged Projects
    // =============================================================================

    public async Task<PaginatedResponse<ProjectResponse>> GetPagedAsync(
        Guid tenantId,
        int page = 1,
        int pageSize = 20,
        ProjectStatus? status = null,
        CancellationToken cancellationToken = default)
    {
        var (items, total) = await _unitOfWork.Projects.GetPagedAsync(
            page,
            pageSize,
            p => p.TenantId == tenantId && (status == null || p.Status == status),
            p => p.UpdatedAt,
            ascending: false,
            cancellationToken);

        var totalPages = (int)Math.Ceiling(total / (double)pageSize);

        return new PaginatedResponse<ProjectResponse>(
            items.Select(MapToResponse).ToList(),
            total,
            page,
            pageSize,
            totalPages
        );
    }

    // =============================================================================
    // Update Project
    // =============================================================================

    public async Task<ProjectResponse?> UpdateAsync(
        Guid id,
        UpdateProjectRequest request,
        CancellationToken cancellationToken = default)
    {
        var project = await _unitOfWork.Projects.GetByIdAsync(id, cancellationToken);
        
        if (project == null)
            return null;

        // Apply updates
        if (request.Name != null)
            project.Name = request.Name;
        
        if (request.Objective != null)
            project.Objective = request.Objective;
        
        if (request.Status.HasValue)
            project.Status = request.Status.Value;
        
        if (request.LlmProvider.HasValue)
            project.LlmProvider = request.LlmProvider.Value;
        
        if (request.LlmModel != null)
            project.LlmModel = request.LlmModel;
        
        if (request.LlmTemperature.HasValue)
            project.LlmTemperature = request.LlmTemperature.Value;

        _unitOfWork.Projects.Update(project);
        await _unitOfWork.SaveChangesAsync(cancellationToken);

        _logger.LogInformation("Updated project {ProjectId}", project.Id);

        return MapToResponse(project);
    }

    // =============================================================================
    // Delete Project
    // =============================================================================

    public async Task<bool> DeleteAsync(Guid id, CancellationToken cancellationToken = default)
    {
        var project = await _unitOfWork.Projects.GetByIdAsync(id, cancellationToken);
        
        if (project == null)
            return false;

        _unitOfWork.Projects.Remove(project);
        await _unitOfWork.SaveChangesAsync(cancellationToken);

        _logger.LogInformation("Deleted project {ProjectId}", id);

        return true;
    }

    // =============================================================================
    // Update QA Answers
    // =============================================================================

    public async Task<ProjectDetailResponse?> UpdateQaAnswersAsync(
        Guid projectId,
        IReadOnlyList<ProjectQaAnswerRequest> answers,
        CancellationToken cancellationToken = default)
    {
        var project = await _unitOfWork.Projects.GetWithFullDetailsAsync(projectId, cancellationToken);
        
        if (project == null)
            return null;

        // Update or create answers
        foreach (var answerRequest in answers)
        {
            var existing = project.QaAnswers
                .FirstOrDefault(qa => qa.QuestionKey == answerRequest.QuestionKey);

            if (existing != null)
            {
                existing.Answer = answerRequest.Answer;
            }
            else
            {
                project.QaAnswers.Add(new ProjectQaAnswer
                {
                    QuestionKey = answerRequest.QuestionKey,
                    Answer = answerRequest.Answer,
                    ProjectId = projectId
                });
            }
        }

        await _unitOfWork.SaveChangesAsync(cancellationToken);

        return MapToDetailResponse(project);
    }

    // =============================================================================
    // Helper Methods
    // =============================================================================

    private static string GenerateSlug(string name)
    {
        return name
            .ToLowerInvariant()
            .Replace(" ", "-")
            .Replace("_", "-")
            .Where(c => char.IsLetterOrDigit(c) || c == '-')
            .Aggregate("", (s, c) => s + c)
            .Trim('-');
    }

    private static string GenerateCardCodePrefix(string slug)
    {
        var words = slug.Split('-', StringSplitOptions.RemoveEmptyEntries);
        
        if (words.Length >= 2)
        {
            // Take first letter of first two words
            return (words[0][..1] + words[1][..1]).ToUpperInvariant();
        }
        
        // Take first 2-4 characters
        return slug[..Math.Min(4, slug.Length)].ToUpperInvariant();
    }

    private static ProjectResponse MapToResponse(Project project)
    {
        return new ProjectResponse(
            project.Id,
            project.Name,
            project.Slug,
            project.Objective,
            project.Status,
            project.CardCodePrefix,
            project.Skills?.Count ?? 0,
            project.Phases?.SelectMany(p => p.Cards).Count() ?? 0,
            project.CreatedAt,
            project.UpdatedAt
        );
    }

    private static ProjectDetailResponse MapToDetailResponse(Project project)
    {
        return new ProjectDetailResponse(
            project.Id,
            project.Name,
            project.Slug,
            project.Objective,
            project.Status,
            project.CardCodePrefix,
            project.LlmProvider,
            project.LlmModel,
            project.LlmTemperature,
            project.QaAnswers.Select(qa => new ProjectQaAnswerResponse(
                qa.QuestionKey,
                qa.Answer,
                qa.IsRequired
            )).ToList(),
            project.TechChoices.Select(tc => new ProjectTechChoiceResponse(
                tc.TechItemId,
                tc.TechItem.Dimension.Code,
                tc.TechItem.Code,
                tc.TechItem.Name,
                tc.Notes
            )).ToList(),
            project.Skills.Select(s => new SkillSummaryResponse(
                s.Id,
                s.Slug,
                s.Name,
                s.Kind,
                s.Resources.Count
            )).ToList(),
            project.Phases.OrderBy(p => p.Order).Select(p => new PhaseSummaryResponse(
                p.Id,
                p.Code,
                p.Title,
                p.Order,
                p.Cards.Count
            )).ToList(),
            project.CreatedAt,
            project.UpdatedAt
        );
    }
}
