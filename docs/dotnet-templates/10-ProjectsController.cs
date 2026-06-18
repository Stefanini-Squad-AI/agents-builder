// =============================================================================
// ProjectsController.cs - REST API Controller
// =============================================================================
// Location: AgentsWorkshop.Api/Controllers/ProjectsController.cs
// =============================================================================

using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Authorization;
using AgentsWorkshop.Contracts;
using AgentsWorkshop.Contracts.Requests;
using AgentsWorkshop.Contracts.Responses;
using AgentsWorkshop.Core.Interfaces;
using AgentsWorkshop.Domain.Enums;

namespace AgentsWorkshop.Api.Controllers;

/// <summary>
/// Projects API endpoints.
/// </summary>
[ApiController]
[Route("api/[controller]")]
[Produces("application/json")]
public class ProjectsController : ControllerBase
{
    private readonly IProjectService _projectService;
    private readonly IValidationService _validationService;
    private readonly IExportService _exportService;
    private readonly ILogger<ProjectsController> _logger;

    public ProjectsController(
        IProjectService projectService,
        IValidationService validationService,
        IExportService exportService,
        ILogger<ProjectsController> logger)
    {
        _projectService = projectService;
        _validationService = validationService;
        _exportService = exportService;
        _logger = logger;
    }

    // =============================================================================
    // GET /api/projects
    // =============================================================================

    /// <summary>
    /// Get paginated list of projects.
    /// </summary>
    [HttpGet]
    [ProducesResponseType(typeof(PaginatedResponse<ProjectResponse>), StatusCodes.Status200OK)]
    public async Task<ActionResult<PaginatedResponse<ProjectResponse>>> GetProjects(
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20,
        [FromQuery] ProjectStatus? status = null,
        CancellationToken cancellationToken = default)
    {
        // TODO: Get tenant ID from authenticated user
        var tenantId = GetCurrentTenantId();

        var result = await _projectService.GetPagedAsync(
            tenantId, page, pageSize, status, cancellationToken);

        return Ok(result);
    }

    // =============================================================================
    // GET /api/projects/{id}
    // =============================================================================

    /// <summary>
    /// Get project by ID with full details.
    /// </summary>
    [HttpGet("{id:guid}")]
    [ProducesResponseType(typeof(ProjectDetailResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<ProjectDetailResponse>> GetProject(
        Guid id,
        CancellationToken cancellationToken = default)
    {
        var project = await _projectService.GetByIdAsync(id, cancellationToken);

        if (project == null)
            return NotFound();

        return Ok(project);
    }

    // =============================================================================
    // GET /api/projects/slug/{slug}
    // =============================================================================

    /// <summary>
    /// Get project by slug.
    /// </summary>
    [HttpGet("slug/{slug}")]
    [ProducesResponseType(typeof(ProjectResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<ProjectResponse>> GetProjectBySlug(
        string slug,
        CancellationToken cancellationToken = default)
    {
        var project = await _projectService.GetBySlugAsync(slug, cancellationToken);

        if (project == null)
            return NotFound();

        return Ok(project);
    }

    // =============================================================================
    // POST /api/projects
    // =============================================================================

    /// <summary>
    /// Create a new project.
    /// </summary>
    [HttpPost]
    [ProducesResponseType(typeof(ProjectResponse), StatusCodes.Status201Created)]
    [ProducesResponseType(typeof(ValidationProblemDetails), StatusCodes.Status400BadRequest)]
    public async Task<ActionResult<ProjectResponse>> CreateProject(
        [FromBody] CreateProjectRequest request,
        CancellationToken cancellationToken = default)
    {
        var tenantId = GetCurrentTenantId();

        var project = await _projectService.CreateAsync(tenantId, request, cancellationToken);

        return CreatedAtAction(
            nameof(GetProject),
            new { id = project.Id },
            project);
    }

    // =============================================================================
    // PUT /api/projects/{id}
    // =============================================================================

    /// <summary>
    /// Update an existing project.
    /// </summary>
    [HttpPut("{id:guid}")]
    [ProducesResponseType(typeof(ProjectResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<ProjectResponse>> UpdateProject(
        Guid id,
        [FromBody] UpdateProjectRequest request,
        CancellationToken cancellationToken = default)
    {
        var project = await _projectService.UpdateAsync(id, request, cancellationToken);

        if (project == null)
            return NotFound();

        return Ok(project);
    }

    // =============================================================================
    // DELETE /api/projects/{id}
    // =============================================================================

    /// <summary>
    /// Delete a project.
    /// </summary>
    [HttpDelete("{id:guid}")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> DeleteProject(
        Guid id,
        CancellationToken cancellationToken = default)
    {
        var deleted = await _projectService.DeleteAsync(id, cancellationToken);

        if (!deleted)
            return NotFound();

        return NoContent();
    }

    // =============================================================================
    // PUT /api/projects/{id}/qa-answers
    // =============================================================================

    /// <summary>
    /// Update project QA answers.
    /// </summary>
    [HttpPut("{id:guid}/qa-answers")]
    [ProducesResponseType(typeof(ProjectDetailResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<ProjectDetailResponse>> UpdateQaAnswers(
        Guid id,
        [FromBody] IReadOnlyList<ProjectQaAnswerRequest> answers,
        CancellationToken cancellationToken = default)
    {
        var project = await _projectService.UpdateQaAnswersAsync(id, answers, cancellationToken);

        if (project == null)
            return NotFound();

        return Ok(project);
    }

    // =============================================================================
    // GET /api/projects/{id}/validate
    // =============================================================================

    /// <summary>
    /// Validate project for export.
    /// </summary>
    [HttpGet("{id:guid}/validate")]
    [ProducesResponseType(typeof(ValidationResultResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<ValidationResultResponse>> ValidateProject(
        Guid id,
        CancellationToken cancellationToken = default)
    {
        var result = await _validationService.ValidateProjectAsync(id, cancellationToken);
        return Ok(result);
    }

    // =============================================================================
    // POST /api/projects/{id}/export
    // =============================================================================

    /// <summary>
    /// Export project to filesystem or zip.
    /// </summary>
    [HttpPost("{id:guid}/export")]
    [ProducesResponseType(typeof(ExportResultResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(typeof(ValidationResultResponse), StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<ExportResultResponse>> ExportProject(
        Guid id,
        [FromBody] ExportRequest? request = null,
        CancellationToken cancellationToken = default)
    {
        request ??= new ExportRequest();

        // Validate first
        var validation = await _validationService.ValidateProjectAsync(id, cancellationToken);
        
        if (!validation.IsValid)
        {
            return BadRequest(validation);
        }

        var result = await _exportService.ExportProjectAsync(id, request, cancellationToken);
        return Ok(result);
    }

    // =============================================================================
    // GET /api/projects/{id}/export/zip
    // =============================================================================

    /// <summary>
    /// Download project export as ZIP file.
    /// </summary>
    [HttpGet("{id:guid}/export/zip")]
    [ProducesResponseType(typeof(FileContentResult), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> ExportProjectZip(
        Guid id,
        CancellationToken cancellationToken = default)
    {
        var project = await _projectService.GetByIdAsync(id, cancellationToken);
        
        if (project == null)
            return NotFound();

        var zipBytes = await _exportService.ExportToZipAsync(id, cancellationToken);
        
        return File(
            zipBytes,
            "application/zip",
            $"{project.Slug}-export.zip");
    }

    // =============================================================================
    // Helper Methods
    // =============================================================================

    private Guid GetCurrentTenantId()
    {
        // TODO: Extract from JWT claims or auth context
        // For now, return a default tenant
        return Guid.Parse("00000000-0000-0000-0000-000000000001");
    }
}

// =============================================================================
// SkillsController.cs
// =============================================================================

[ApiController]
[Route("api/projects/{projectId:guid}/[controller]")]
[Produces("application/json")]
public class SkillsController : ControllerBase
{
    private readonly ISkillService _skillService;
    private readonly ILogger<SkillsController> _logger;

    public SkillsController(ISkillService skillService, ILogger<SkillsController> logger)
    {
        _skillService = skillService;
        _logger = logger;
    }

    [HttpGet]
    [ProducesResponseType(typeof(IReadOnlyList<SkillSummaryResponse>), StatusCodes.Status200OK)]
    public async Task<ActionResult<IReadOnlyList<SkillSummaryResponse>>> GetSkills(
        Guid projectId,
        CancellationToken cancellationToken = default)
    {
        var skills = await _skillService.GetByProjectAsync(projectId, cancellationToken);
        return Ok(skills);
    }

    [HttpGet("{id:guid}")]
    [ProducesResponseType(typeof(SkillDetailResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<SkillDetailResponse>> GetSkill(
        Guid projectId,
        Guid id,
        CancellationToken cancellationToken = default)
    {
        var skill = await _skillService.GetByIdAsync(id, cancellationToken);
        
        if (skill == null)
            return NotFound();

        return Ok(skill);
    }

    [HttpGet("slug/{slug}")]
    [ProducesResponseType(typeof(SkillDetailResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<SkillDetailResponse>> GetSkillBySlug(
        Guid projectId,
        string slug,
        CancellationToken cancellationToken = default)
    {
        var skill = await _skillService.GetBySlugAsync(projectId, slug, cancellationToken);
        
        if (skill == null)
            return NotFound();

        return Ok(skill);
    }

    [HttpPost]
    [ProducesResponseType(typeof(SkillDetailResponse), StatusCodes.Status201Created)]
    [ProducesResponseType(typeof(ValidationProblemDetails), StatusCodes.Status400BadRequest)]
    public async Task<ActionResult<SkillDetailResponse>> CreateSkill(
        Guid projectId,
        [FromBody] CreateSkillRequest request,
        CancellationToken cancellationToken = default)
    {
        var skill = await _skillService.CreateAsync(projectId, request, cancellationToken);

        return CreatedAtAction(
            nameof(GetSkill),
            new { projectId, id = skill.Id },
            skill);
    }

    [HttpPut("{id:guid}")]
    [ProducesResponseType(typeof(SkillDetailResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<SkillDetailResponse>> UpdateSkill(
        Guid projectId,
        Guid id,
        [FromBody] UpdateSkillRequest request,
        CancellationToken cancellationToken = default)
    {
        var skill = await _skillService.UpdateAsync(id, request, cancellationToken);
        
        if (skill == null)
            return NotFound();

        return Ok(skill);
    }

    [HttpDelete("{id:guid}")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> DeleteSkill(
        Guid projectId,
        Guid id,
        CancellationToken cancellationToken = default)
    {
        var deleted = await _skillService.DeleteAsync(id, cancellationToken);
        
        if (!deleted)
            return NotFound();

        return NoContent();
    }

    [HttpPost("{id:guid}/resources")]
    [ProducesResponseType(typeof(SkillDetailResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<SkillDetailResponse>> AddResource(
        Guid projectId,
        Guid id,
        [FromBody] SkillResourceRequest resource,
        CancellationToken cancellationToken = default)
    {
        var skill = await _skillService.AddResourceAsync(id, resource, cancellationToken);
        
        if (skill == null)
            return NotFound();

        return Ok(skill);
    }
}

// =============================================================================
// BacklogController.cs
// =============================================================================

[ApiController]
[Route("api/projects/{projectId:guid}/backlog")]
[Produces("application/json")]
public class BacklogController : ControllerBase
{
    private readonly IBacklogService _backlogService;
    private readonly ILogger<BacklogController> _logger;

    public BacklogController(IBacklogService backlogService, ILogger<BacklogController> logger)
    {
        _backlogService = backlogService;
        _logger = logger;
    }

    // =============================================================================
    // Phase Endpoints
    // =============================================================================

    [HttpGet("phases")]
    [ProducesResponseType(typeof(IReadOnlyList<PhaseDetailResponse>), StatusCodes.Status200OK)]
    public async Task<ActionResult<IReadOnlyList<PhaseDetailResponse>>> GetPhases(
        Guid projectId,
        CancellationToken cancellationToken = default)
    {
        var phases = await _backlogService.GetPhasesByProjectAsync(projectId, cancellationToken);
        return Ok(phases);
    }

    [HttpPost("phases")]
    [ProducesResponseType(typeof(PhaseDetailResponse), StatusCodes.Status201Created)]
    public async Task<ActionResult<PhaseDetailResponse>> CreatePhase(
        Guid projectId,
        [FromBody] CreatePhaseRequest request,
        CancellationToken cancellationToken = default)
    {
        var phase = await _backlogService.CreatePhaseAsync(projectId, request, cancellationToken);
        return CreatedAtAction(nameof(GetPhases), new { projectId }, phase);
    }

    [HttpPut("phases/{phaseId:guid}/reorder")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    public async Task<IActionResult> ReorderPhases(
        Guid projectId,
        [FromBody] IReadOnlyList<Guid> phaseIds,
        CancellationToken cancellationToken = default)
    {
        await _backlogService.ReorderPhasesAsync(projectId, phaseIds, cancellationToken);
        return NoContent();
    }

    // =============================================================================
    // Card Endpoints
    // =============================================================================

    [HttpGet("phases/{phaseId:guid}/cards")]
    [ProducesResponseType(typeof(IReadOnlyList<CardSummaryResponse>), StatusCodes.Status200OK)]
    public async Task<ActionResult<IReadOnlyList<CardSummaryResponse>>> GetCards(
        Guid projectId,
        Guid phaseId,
        CancellationToken cancellationToken = default)
    {
        var cards = await _backlogService.GetCardsByPhaseAsync(phaseId, cancellationToken);
        return Ok(cards);
    }

    [HttpGet("cards/{cardId:guid}")]
    [ProducesResponseType(typeof(CardDetailResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<CardDetailResponse>> GetCard(
        Guid projectId,
        Guid cardId,
        CancellationToken cancellationToken = default)
    {
        var card = await _backlogService.GetCardByIdAsync(cardId, cancellationToken);
        
        if (card == null)
            return NotFound();

        return Ok(card);
    }

    [HttpPost("phases/{phaseId:guid}/cards")]
    [ProducesResponseType(typeof(CardDetailResponse), StatusCodes.Status201Created)]
    public async Task<ActionResult<CardDetailResponse>> CreateCard(
        Guid projectId,
        Guid phaseId,
        [FromBody] CreateCardRequest request,
        CancellationToken cancellationToken = default)
    {
        var card = await _backlogService.CreateCardAsync(phaseId, request, cancellationToken);
        return CreatedAtAction(nameof(GetCard), new { projectId, cardId = card.Id }, card);
    }

    [HttpPut("cards/{cardId:guid}")]
    [ProducesResponseType(typeof(CardDetailResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<CardDetailResponse>> UpdateCard(
        Guid projectId,
        Guid cardId,
        [FromBody] UpdateCardRequest request,
        CancellationToken cancellationToken = default)
    {
        var card = await _backlogService.UpdateCardAsync(cardId, request, cancellationToken);
        
        if (card == null)
            return NotFound();

        return Ok(card);
    }

    [HttpDelete("cards/{cardId:guid}")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> DeleteCard(
        Guid projectId,
        Guid cardId,
        CancellationToken cancellationToken = default)
    {
        var deleted = await _backlogService.DeleteCardAsync(cardId, cancellationToken);
        
        if (!deleted)
            return NotFound();

        return NoContent();
    }

    // =============================================================================
    // DAG Visualization
    // =============================================================================

    [HttpGet("dag")]
    [ProducesResponseType(typeof(DagGraphResponse), StatusCodes.Status200OK)]
    public async Task<ActionResult<DagGraphResponse>> GetDag(
        Guid projectId,
        CancellationToken cancellationToken = default)
    {
        var dag = await _backlogService.GetDagAsync(projectId, cancellationToken);
        return Ok(dag);
    }
}
