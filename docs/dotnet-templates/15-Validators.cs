// =============================================================================
// FluentValidation - Request Validators
// =============================================================================
// Location: AgentsWorkshop.Api/Validators/
// Replaces: Pydantic validation
// =============================================================================

using FluentValidation;
using AgentsWorkshop.Contracts.Requests;
using AgentsWorkshop.Domain.Enums;

namespace AgentsWorkshop.Api.Validators;

// =============================================================================
// Project Validators
// =============================================================================

public class CreateProjectRequestValidator : AbstractValidator<CreateProjectRequest>
{
    public CreateProjectRequestValidator()
    {
        RuleFor(x => x.Name)
            .NotEmpty().WithMessage("Project name is required")
            .MaximumLength(200).WithMessage("Project name cannot exceed 200 characters")
            .Matches(@"^[a-zA-Z0-9\s\-_]+$").WithMessage("Project name can only contain letters, numbers, spaces, hyphens, and underscores");

        RuleFor(x => x.Objective)
            .MaximumLength(2000).WithMessage("Objective cannot exceed 2000 characters")
            .When(x => x.Objective != null);
    }
}

public class UpdateProjectRequestValidator : AbstractValidator<UpdateProjectRequest>
{
    public UpdateProjectRequestValidator()
    {
        RuleFor(x => x.Name)
            .MaximumLength(200).WithMessage("Project name cannot exceed 200 characters")
            .When(x => x.Name != null);

        RuleFor(x => x.Objective)
            .MaximumLength(2000).WithMessage("Objective cannot exceed 2000 characters")
            .When(x => x.Objective != null);

        RuleFor(x => x.LlmTemperature)
            .InclusiveBetween(0.0m, 2.0m).WithMessage("Temperature must be between 0.0 and 2.0")
            .When(x => x.LlmTemperature.HasValue);
    }
}

// =============================================================================
// Skill Validators
// =============================================================================

public class CreateSkillRequestValidator : AbstractValidator<CreateSkillRequest>
{
    public CreateSkillRequestValidator()
    {
        RuleFor(x => x.Slug)
            .NotEmpty().WithMessage("Slug is required")
            .MaximumLength(100).WithMessage("Slug cannot exceed 100 characters")
            .Matches(@"^[a-z0-9\-]+$").WithMessage("Slug must be lowercase letters, numbers, and hyphens only");

        RuleFor(x => x.Name)
            .NotEmpty().WithMessage("Name is required")
            .MaximumLength(200).WithMessage("Name cannot exceed 200 characters");

        RuleFor(x => x.Description)
            .MaximumLength(2000).WithMessage("Description cannot exceed 2000 characters")
            .When(x => x.Description != null);

        RuleFor(x => x.Kind)
            .IsInEnum().WithMessage("Invalid skill kind");

        // Analyzer skills should have description with trigger phrases
        RuleFor(x => x.Description)
            .Must(desc => desc != null && (desc.Contains("Use when") || desc.Contains("Trigger when")))
            .WithMessage("Analyzer skills should have a description with trigger phrases ('Use when...' or 'Trigger when...')")
            .When(x => x.Kind == SkillKind.Analyzer);

        RuleForEach(x => x.Resources)
            .SetValidator(new SkillResourceRequestValidator())
            .When(x => x.Resources != null);
    }
}

public class SkillResourceRequestValidator : AbstractValidator<SkillResourceRequest>
{
    public SkillResourceRequestValidator()
    {
        RuleFor(x => x.Filename)
            .NotEmpty().WithMessage("Filename is required")
            .MaximumLength(255).WithMessage("Filename cannot exceed 255 characters")
            .Matches(@"^[a-zA-Z0-9\-_.]+$").WithMessage("Filename can only contain letters, numbers, hyphens, underscores, and dots");

        RuleFor(x => x.Language)
            .IsInEnum().WithMessage("Invalid resource language");

        RuleFor(x => x.Content)
            .NotEmpty().WithMessage("Content is required");
    }
}

// =============================================================================
// Card Validators
// =============================================================================

public class CreateCardRequestValidator : AbstractValidator<CreateCardRequest>
{
    public CreateCardRequestValidator()
    {
        RuleFor(x => x.Code)
            .NotEmpty().WithMessage("Card code is required")
            .MaximumLength(20).WithMessage("Card code cannot exceed 20 characters")
            .Matches(@"^[A-Z]{2,8}-\d{3}$").WithMessage("Card code must match pattern: PREFIX-NNN (e.g., PROJ-101)");

        RuleFor(x => x.Title)
            .NotEmpty().WithMessage("Title is required")
            .MaximumLength(300).WithMessage("Title cannot exceed 300 characters");

        RuleFor(x => x.Type)
            .IsInEnum().WithMessage("Invalid card type");

        RuleFor(x => x.StoryPoints)
            .InclusiveBetween(1, 21).WithMessage("Story points must be between 1 and 21 (Fibonacci scale)")
            .When(x => x.StoryPoints.HasValue);

        // Every card MUST have at least 1 skill
        RuleFor(x => x.SkillSlugs)
            .NotEmpty().WithMessage("At least one skill is required for each card");

        // human_gate requires checklist
        RuleFor(x => x.HumanGateChecklistMd)
            .NotEmpty().WithMessage("Human gate checklist is required when human_gate is true")
            .When(x => x.HumanGate);

        RuleForEach(x => x.SkillSlugs)
            .NotEmpty().WithMessage("Skill slug cannot be empty")
            .Matches(@"^[a-z0-9\-]+$").WithMessage("Skill slug must be lowercase with hyphens");

        RuleForEach(x => x.DependsOnCodes)
            .NotEmpty().WithMessage("Dependency code cannot be empty")
            .Matches(@"^[A-Z]{2,8}-\d{3}$").WithMessage("Dependency code must match card code pattern")
            .When(x => x.DependsOnCodes != null);
    }
}

public class UpdateCardRequestValidator : AbstractValidator<UpdateCardRequest>
{
    public UpdateCardRequestValidator()
    {
        RuleFor(x => x.Title)
            .MaximumLength(300).WithMessage("Title cannot exceed 300 characters")
            .When(x => x.Title != null);

        RuleFor(x => x.Type)
            .IsInEnum().WithMessage("Invalid card type")
            .When(x => x.Type.HasValue);

        RuleFor(x => x.Status)
            .IsInEnum().WithMessage("Invalid card status")
            .When(x => x.Status.HasValue);

        RuleFor(x => x.StoryPoints)
            .InclusiveBetween(1, 21).WithMessage("Story points must be between 1 and 21")
            .When(x => x.StoryPoints.HasValue);

        // If setting human_gate to true, require checklist
        RuleFor(x => x.HumanGateChecklistMd)
            .NotEmpty().WithMessage("Human gate checklist is required when setting human_gate to true")
            .When(x => x.HumanGate == true);

        RuleForEach(x => x.SkillSlugs)
            .NotEmpty().WithMessage("Skill slug cannot be empty")
            .Matches(@"^[a-z0-9\-]+$").WithMessage("Skill slug must be lowercase with hyphens")
            .When(x => x.SkillSlugs != null);
    }
}

// =============================================================================
// Phase Validators
// =============================================================================

public class CreatePhaseRequestValidator : AbstractValidator<CreatePhaseRequest>
{
    public CreatePhaseRequestValidator()
    {
        RuleFor(x => x.Code)
            .NotEmpty().WithMessage("Phase code is required")
            .MaximumLength(100).WithMessage("Phase code cannot exceed 100 characters")
            .Matches(@"^phase-\d+-[a-z\-]+$").WithMessage("Phase code must match pattern: phase-N-name (e.g., phase-1-setup)");

        RuleFor(x => x.Title)
            .NotEmpty().WithMessage("Phase title is required")
            .MaximumLength(200).WithMessage("Phase title cannot exceed 200 characters");

        RuleFor(x => x.Description)
            .MaximumLength(2000).WithMessage("Description cannot exceed 2000 characters")
            .When(x => x.Description != null);

        RuleFor(x => x.Order)
            .GreaterThan(0).WithMessage("Order must be greater than 0")
            .When(x => x.Order.HasValue);
    }
}

// =============================================================================
// QA Answer Validators
// =============================================================================

public class ProjectQaAnswerRequestValidator : AbstractValidator<ProjectQaAnswerRequest>
{
    private static readonly HashSet<string> ValidQuestionKeys = new()
    {
        "business_problem",
        "success_definition", 
        "users_and_actors",
        "scope_boundaries",
        "existing_systems",
        "compliance_requirements",
        "timeline_constraints"
    };

    public ProjectQaAnswerRequestValidator()
    {
        RuleFor(x => x.QuestionKey)
            .NotEmpty().WithMessage("Question key is required")
            .Must(key => ValidQuestionKeys.Contains(key))
            .WithMessage($"Invalid question key. Must be one of: {string.Join(", ", ValidQuestionKeys)}");
    }
}

// =============================================================================
// Export Request Validator
// =============================================================================

public class ExportRequestValidator : AbstractValidator<ExportRequest>
{
    private static readonly HashSet<string> ValidFormats = new() { "filesystem", "zip", "jira_csv" };

    public ExportRequestValidator()
    {
        RuleFor(x => x.Format)
            .Must(f => ValidFormats.Contains(f))
            .WithMessage($"Invalid format. Must be one of: {string.Join(", ", ValidFormats)}");

        RuleFor(x => x.OutputPath)
            .Must(path => path == null || !Path.IsPathRooted(path) || Directory.Exists(Path.GetDirectoryName(path)))
            .WithMessage("Output path directory must exist");
    }
}
