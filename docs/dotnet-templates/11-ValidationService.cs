// =============================================================================
// ValidationService.cs - Business Rule Validation
// =============================================================================
// Location: AgentsWorkshop.Core/Services/ValidationService.cs
// Mirrors: Python validators/ (dag, refs, frontmatter, paths)
// =============================================================================

using Microsoft.Extensions.Logging;
using AgentsWorkshop.Contracts.Responses;
using AgentsWorkshop.Core.Interfaces;
using AgentsWorkshop.Domain.Entities;
using AgentsWorkshop.Domain.Enums;

namespace AgentsWorkshop.Core.Services;

public class ValidationService : IValidationService
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<ValidationService> _logger;

    public ValidationService(IUnitOfWork unitOfWork, ILogger<ValidationService> logger)
    {
        _unitOfWork = unitOfWork;
        _logger = logger;
    }

    // =============================================================================
    // Validate Full Project
    // =============================================================================

    public async Task<ValidationResultResponse> ValidateProjectAsync(
        Guid projectId,
        CancellationToken cancellationToken = default)
    {
        var issues = new List<ValidationIssueResponse>();

        var project = await _unitOfWork.Projects.GetWithFullDetailsAsync(projectId, cancellationToken);
        
        if (project == null)
        {
            return new ValidationResultResponse(false, 1, 0, new[]
            {
                new ValidationIssueResponse(
                    ValidationSeverity.Error,
                    "PROJECT_NOT_FOUND",
                    "Project not found",
                    "Project",
                    projectId.ToString(),
                    null)
            });
        }

        // Validate required QA answers (§4.5)
        var requiredQuestions = new[] { "business_problem", "success_definition", "users_and_actors" };
        foreach (var questionKey in requiredQuestions)
        {
            var answer = project.QaAnswers.FirstOrDefault(qa => qa.QuestionKey == questionKey);
            if (answer == null || string.IsNullOrWhiteSpace(answer.Answer))
            {
                issues.Add(new ValidationIssueResponse(
                    ValidationSeverity.Error,
                    "REQUIRED_QA_MISSING",
                    $"Required question '{questionKey}' is not answered",
                    "ProjectQaAnswer",
                    null,
                    questionKey));
            }
        }

        // Validate each skill
        foreach (var skill in project.Skills)
        {
            var skillIssues = ValidateSkillInternal(skill);
            issues.AddRange(skillIssues);
        }

        // Validate each card
        var allCards = project.Phases.SelectMany(p => p.Cards).ToList();
        foreach (var card in allCards)
        {
            var cardIssues = ValidateCardInternal(card, allCards);
            issues.AddRange(cardIssues);
        }

        // Validate phases
        foreach (var phase in project.Phases)
        {
            var phaseIssues = ValidatePhaseInternal(phase);
            issues.AddRange(phaseIssues);
        }

        // Validate DAG
        var dagIssues = await ValidateDagInternal(project, allCards);
        issues.AddRange(dagIssues);

        var errorCount = issues.Count(i => i.Severity == ValidationSeverity.Error);
        var warningCount = issues.Count(i => i.Severity == ValidationSeverity.Warning);

        return new ValidationResultResponse(
            errorCount == 0,
            errorCount,
            warningCount,
            issues);
    }

    // =============================================================================
    // Validate Skill (§4.2, §8)
    // =============================================================================

    public async Task<ValidationResultResponse> ValidateSkillAsync(
        Guid skillId,
        CancellationToken cancellationToken = default)
    {
        var skill = await _unitOfWork.Skills.GetWithResourcesAsync(skillId, cancellationToken);
        
        if (skill == null)
        {
            return new ValidationResultResponse(false, 1, 0, new[]
            {
                new ValidationIssueResponse(
                    ValidationSeverity.Error,
                    "SKILL_NOT_FOUND",
                    "Skill not found",
                    "Skill",
                    skillId.ToString(),
                    null)
            });
        }

        var issues = ValidateSkillInternal(skill);
        var errorCount = issues.Count(i => i.Severity == ValidationSeverity.Error);
        var warningCount = issues.Count(i => i.Severity == ValidationSeverity.Warning);

        return new ValidationResultResponse(errorCount == 0, errorCount, warningCount, issues);
    }

    private List<ValidationIssueResponse> ValidateSkillInternal(Skill skill)
    {
        var issues = new List<ValidationIssueResponse>();

        // Analyzer skill with 0 resources → WARNING (§4.2)
        if (skill.Kind == SkillKind.Analyzer && !skill.Resources.Any())
        {
            issues.Add(new ValidationIssueResponse(
                ValidationSeverity.Warning,
                "ANALYZER_NO_RESOURCES",
                $"Analyzer skill '{skill.Slug}' has no resources",
                "Skill",
                skill.Id.ToString(),
                "Resources"));
        }

        // Validate body is not empty for non-context skills
        if (skill.Kind != SkillKind.Context && string.IsNullOrWhiteSpace(skill.Body))
        {
            issues.Add(new ValidationIssueResponse(
                ValidationSeverity.Warning,
                "SKILL_EMPTY_BODY",
                $"Skill '{skill.Slug}' has an empty body",
                "Skill",
                skill.Id.ToString(),
                "Body"));
        }

        return issues;
    }

    // =============================================================================
    // Validate Card (§4.2, §5.2, §9)
    // =============================================================================

    public async Task<ValidationResultResponse> ValidateCardAsync(
        Guid cardId,
        CancellationToken cancellationToken = default)
    {
        var card = await _unitOfWork.Cards.GetWithFullDetailsAsync(cardId, cancellationToken);
        
        if (card == null)
        {
            return new ValidationResultResponse(false, 1, 0, new[]
            {
                new ValidationIssueResponse(
                    ValidationSeverity.Error,
                    "CARD_NOT_FOUND",
                    "Card not found",
                    "Card",
                    cardId.ToString(),
                    null)
            });
        }

        var allCards = await _unitOfWork.Cards.GetByProjectAsync(card.ProjectId, cancellationToken);
        var issues = ValidateCardInternal(card, allCards.ToList());
        
        var errorCount = issues.Count(i => i.Severity == ValidationSeverity.Error);
        var warningCount = issues.Count(i => i.Severity == ValidationSeverity.Warning);

        return new ValidationResultResponse(errorCount == 0, errorCount, warningCount, issues);
    }

    private List<ValidationIssueResponse> ValidateCardInternal(Card card, List<Card> allCards)
    {
        var issues = new List<ValidationIssueResponse>();

        // Every card MUST have ≥1 skill → ERROR (§4.2)
        if (!card.CardSkills.Any())
        {
            issues.Add(new ValidationIssueResponse(
                ValidationSeverity.Error,
                "CARD_NO_SKILLS",
                $"Card '{card.Code}' has no linked skills",
                "Card",
                card.Id.ToString(),
                "Skills"));
        }

        // human_gate=true requires non-empty checklist (CHECK constraint)
        if (card.HumanGate && string.IsNullOrWhiteSpace(card.HumanGateChecklistMd))
        {
            issues.Add(new ValidationIssueResponse(
                ValidationSeverity.Error,
                "HUMAN_GATE_NO_CHECKLIST",
                $"Card '{card.Code}' has human_gate=true but no checklist",
                "Card",
                card.Id.ToString(),
                "HumanGateChecklistMd"));
        }

        // All depends_on references MUST resolve → ERROR (§9)
        foreach (var dep in card.Dependencies)
        {
            var depCard = allCards.FirstOrDefault(c => c.Id == dep.DependsOnCardId);
            if (depCard == null)
            {
                issues.Add(new ValidationIssueResponse(
                    ValidationSeverity.Error,
                    "DEPENDENCY_NOT_FOUND",
                    $"Card '{card.Code}' depends on non-existent card",
                    "Card",
                    card.Id.ToString(),
                    "Dependencies"));
            }
        }

        // Forward-phase dependencies forbidden → ERROR (§9)
        foreach (var dep in card.Dependencies)
        {
            var depCard = allCards.FirstOrDefault(c => c.Id == dep.DependsOnCardId);
            if (depCard != null && depCard.Phase.Order > card.Phase.Order)
            {
                issues.Add(new ValidationIssueResponse(
                    ValidationSeverity.Error,
                    "FORWARD_PHASE_DEPENDENCY",
                    $"Card '{card.Code}' depends on card '{depCard.Code}' from a later phase",
                    "Card",
                    card.Id.ToString(),
                    "Dependencies"));
            }
        }

        return issues;
    }

    private List<ValidationIssueResponse> ValidatePhaseInternal(Phase phase)
    {
        var issues = new List<ValidationIssueResponse>();

        // Phase must have ≥1 card → WARNING
        if (!phase.Cards.Any())
        {
            issues.Add(new ValidationIssueResponse(
                ValidationSeverity.Warning,
                "PHASE_EMPTY",
                $"Phase '{phase.Code}' has no cards",
                "Phase",
                phase.Id.ToString(),
                null));
        }

        // Last card of phase SHOULD have human_gate=true → WARNING (§9)
        var lastCard = phase.Cards.OrderByDescending(c => c.Code).FirstOrDefault();
        if (lastCard != null && !lastCard.HumanGate)
        {
            issues.Add(new ValidationIssueResponse(
                ValidationSeverity.Warning,
                "PHASE_LAST_CARD_NO_GATE",
                $"Last card '{lastCard.Code}' of phase '{phase.Code}' should have human_gate=true",
                "Card",
                lastCard.Id.ToString(),
                "HumanGate"));
        }

        return issues;
    }

    // =============================================================================
    // Validate DAG (§9) - Kahn's Algorithm for Cycle Detection
    // =============================================================================

    public async Task<ValidationResultResponse> ValidateDagAsync(
        Guid projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await _unitOfWork.Projects.GetWithFullDetailsAsync(projectId, cancellationToken);
        
        if (project == null)
        {
            return new ValidationResultResponse(false, 1, 0, new[]
            {
                new ValidationIssueResponse(
                    ValidationSeverity.Error,
                    "PROJECT_NOT_FOUND",
                    "Project not found",
                    "Project",
                    projectId.ToString(),
                    null)
            });
        }

        var allCards = project.Phases.SelectMany(p => p.Cards).ToList();
        var issues = await ValidateDagInternal(project, allCards);
        
        var errorCount = issues.Count(i => i.Severity == ValidationSeverity.Error);
        var warningCount = issues.Count(i => i.Severity == ValidationSeverity.Warning);

        return new ValidationResultResponse(errorCount == 0, errorCount, warningCount, issues);
    }

    private Task<List<ValidationIssueResponse>> ValidateDagInternal(Project project, List<Card> allCards)
    {
        var issues = new List<ValidationIssueResponse>();

        // Build adjacency list and in-degree map
        var inDegree = allCards.ToDictionary(c => c.Id, _ => 0);
        var adjacency = allCards.ToDictionary(c => c.Id, _ => new List<Guid>());

        foreach (var card in allCards)
        {
            foreach (var dep in card.Dependencies)
            {
                if (adjacency.ContainsKey(dep.DependsOnCardId))
                {
                    adjacency[dep.DependsOnCardId].Add(card.Id);
                    inDegree[card.Id]++;
                }
            }
        }

        // Kahn's algorithm
        var queue = new Queue<Guid>();
        foreach (var (id, degree) in inDegree)
        {
            if (degree == 0)
                queue.Enqueue(id);
        }

        var processed = 0;
        while (queue.Count > 0)
        {
            var current = queue.Dequeue();
            processed++;

            foreach (var neighbor in adjacency[current])
            {
                inDegree[neighbor]--;
                if (inDegree[neighbor] == 0)
                    queue.Enqueue(neighbor);
            }
        }

        // If not all nodes processed, there's a cycle
        if (processed != allCards.Count)
        {
            var cyclicCards = allCards
                .Where(c => inDegree[c.Id] > 0)
                .Select(c => c.Code);

            issues.Add(new ValidationIssueResponse(
                ValidationSeverity.Error,
                "DAG_CYCLE_DETECTED",
                $"Cyclic dependencies detected involving cards: {string.Join(", ", cyclicCards)}",
                "Project",
                project.Id.ToString(),
                "Dependencies"));
        }

        return Task.FromResult(issues);
    }

    public async Task<bool> HasCyclicDependenciesAsync(
        Guid projectId,
        CancellationToken cancellationToken = default)
    {
        var result = await ValidateDagAsync(projectId, cancellationToken);
        return result.Issues.Any(i => i.Code == "DAG_CYCLE_DETECTED");
    }
}
