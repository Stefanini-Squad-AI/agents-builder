// =============================================================================
// Domain Entities - Complete Set
// =============================================================================
// Location: AgentsWorkshop.Domain/Entities/
// Mirrors: Python domain models (projects.py, skills.py, backlog.py, etc.)
// =============================================================================

using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using AgentsWorkshop.Domain.Enums;

namespace AgentsWorkshop.Domain.Entities;

// =============================================================================
// Tenant Entity
// =============================================================================
public class Tenant : BaseEntity
{
    [Required]
    [MaxLength(100)]
    public string Name { get; set; } = string.Empty;

    [MaxLength(50)]
    public string? Slug { get; set; }

    // Navigation
    public ICollection<User> Users { get; set; } = new List<User>();
    public ICollection<Project> Projects { get; set; } = new List<Project>();
}

// =============================================================================
// User Entity
// =============================================================================
public class User : BaseEntity
{
    [Required]
    [MaxLength(255)]
    public string Email { get; set; } = string.Empty;

    [MaxLength(100)]
    public string? DisplayName { get; set; }

    public Guid TenantId { get; set; }

    // Navigation
    [ForeignKey(nameof(TenantId))]
    public Tenant Tenant { get; set; } = null!;
}

// =============================================================================
// Project Entity (Central Aggregate Root)
// =============================================================================
public class Project : BaseEntity
{
    [Required]
    [MaxLength(200)]
    public string Name { get; set; } = string.Empty;

    [Required]
    [MaxLength(100)]
    public string Slug { get; set; } = string.Empty;

    [MaxLength(2000)]
    public string? Objective { get; set; }

    public ProjectStatus Status { get; set; } = ProjectStatus.Draft;

    // Card code prefix (2-8 uppercase chars)
    [MaxLength(8)]
    public string? CardCodePrefix { get; set; }

    // LLM Configuration (per-project overrides)
    public LlmProvider? LlmProvider { get; set; }

    [MaxLength(50)]
    public string? LlmModel { get; set; }

    [Range(0.0, 2.0)]
    public decimal? LlmTemperature { get; set; }

    public Guid TenantId { get; set; }

    // Navigation Properties
    [ForeignKey(nameof(TenantId))]
    public Tenant Tenant { get; set; } = null!;

    public ICollection<ProjectArtifact> Artifacts { get; set; } = new List<ProjectArtifact>();
    public ICollection<ProjectQaAnswer> QaAnswers { get; set; } = new List<ProjectQaAnswer>();
    public ICollection<ProjectTechChoice> TechChoices { get; set; } = new List<ProjectTechChoice>();
    public ICollection<Skill> Skills { get; set; } = new List<Skill>();
    public ICollection<Phase> Phases { get; set; } = new List<Phase>();
    public ICollection<Export> Exports { get; set; } = new List<Export>();
}

// =============================================================================
// Project Artifact Entity
// =============================================================================
public class ProjectArtifact : BaseEntity
{
    [Required]
    [MaxLength(500)]
    public string FileName { get; set; } = string.Empty;

    [MaxLength(100)]
    public string? MimeType { get; set; }

    public long? FileSize { get; set; }

    public string? FilePath { get; set; }

    public ExtractionStatus ExtractionStatus { get; set; } = ExtractionStatus.Pending;

    [Column(TypeName = "text")]
    public string? ExtractedText { get; set; }

    public string? ExtractionError { get; set; }

    public Guid ProjectId { get; set; }

    [ForeignKey(nameof(ProjectId))]
    public Project Project { get; set; } = null!;
}

// =============================================================================
// Project QA Answer Entity
// =============================================================================
public class ProjectQaAnswer : BaseEntity
{
    [Required]
    [MaxLength(100)]
    public string QuestionKey { get; set; } = string.Empty;

    [Column(TypeName = "text")]
    public string? Answer { get; set; }

    public bool IsRequired { get; set; }

    public Guid ProjectId { get; set; }

    [ForeignKey(nameof(ProjectId))]
    public Project Project { get; set; } = null!;
}

// =============================================================================
// Skill Entity
// =============================================================================
public class Skill : BaseEntity
{
    [Required]
    [MaxLength(100)]
    public string Slug { get; set; } = string.Empty;

    [Required]
    [MaxLength(200)]
    public string Name { get; set; } = string.Empty;

    [MaxLength(2000)]
    public string? Description { get; set; }

    public SkillKind Kind { get; set; }

    [Column(TypeName = "text")]
    public string? Body { get; set; }

    public Guid ProjectId { get; set; }

    // Navigation
    [ForeignKey(nameof(ProjectId))]
    public Project Project { get; set; } = null!;

    public ICollection<SkillResource> Resources { get; set; } = new List<SkillResource>();
    public ICollection<CardSkill> CardSkills { get; set; } = new List<CardSkill>();
}

// =============================================================================
// Skill Resource Entity
// =============================================================================
public class SkillResource : BaseEntity
{
    [Required]
    [MaxLength(255)]
    public string Filename { get; set; } = string.Empty;

    public ResourceLanguage Language { get; set; } = ResourceLanguage.Markdown;

    [Column(TypeName = "text")]
    public string Content { get; set; } = string.Empty;

    public Guid SkillId { get; set; }

    [ForeignKey(nameof(SkillId))]
    public Skill Skill { get; set; } = null!;
}

// =============================================================================
// Phase Entity
// =============================================================================
public class Phase : BaseEntity
{
    [Required]
    [MaxLength(100)]
    public string Code { get; set; } = string.Empty;

    [Required]
    [MaxLength(200)]
    public string Title { get; set; } = string.Empty;

    [MaxLength(2000)]
    public string? Description { get; set; }

    public int Order { get; set; }

    public Guid ProjectId { get; set; }

    // Navigation
    [ForeignKey(nameof(ProjectId))]
    public Project Project { get; set; } = null!;

    public ICollection<Card> Cards { get; set; } = new List<Card>();
}

// =============================================================================
// Card Entity (Jira-style backlog item)
// =============================================================================
public class Card : BaseEntity
{
    [Required]
    [MaxLength(20)]
    public string Code { get; set; } = string.Empty;

    [Required]
    [MaxLength(300)]
    public string Title { get; set; } = string.Empty;

    public CardType Type { get; set; } = CardType.Task;

    public CardStatus Status { get; set; } = CardStatus.Draft;

    [Range(1, 21)]
    public int? StoryPoints { get; set; }

    // Card sections (markdown content)
    [Column(TypeName = "text")]
    public string? ContextMd { get; set; }

    [Column(TypeName = "text")]
    public string? TaskMd { get; set; }

    [Column(TypeName = "text")]
    public string? OutputsMd { get; set; }

    [Column(TypeName = "text")]
    public string? AcceptanceCriteriaMd { get; set; }

    // Human gate
    public bool HumanGate { get; set; } = false;

    [Column(TypeName = "text")]
    public string? HumanGateChecklistMd { get; set; }

    // Parallel execution flag
    public bool CanRunParallel { get; set; } = false;

    public Guid PhaseId { get; set; }

    public Guid ProjectId { get; set; }

    // Navigation
    [ForeignKey(nameof(PhaseId))]
    public Phase Phase { get; set; } = null!;

    public ICollection<CardSkill> CardSkills { get; set; } = new List<CardSkill>();
    public ICollection<CardDependency> Dependencies { get; set; } = new List<CardDependency>();
    public ICollection<CardInput> Inputs { get; set; } = new List<CardInput>();
}

// =============================================================================
// Card-Skill Junction Table
// =============================================================================
public class CardSkill
{
    public Guid CardId { get; set; }
    public Guid SkillId { get; set; }

    // Navigation
    public Card Card { get; set; } = null!;
    public Skill Skill { get; set; } = null!;
}

// =============================================================================
// Card Dependencies Junction Table
// =============================================================================
public class CardDependency
{
    public Guid CardId { get; set; }
    public Guid DependsOnCardId { get; set; }

    // Navigation
    public Card Card { get; set; } = null!;
    public Card DependsOnCard { get; set; } = null!;
}

// =============================================================================
// Card Input Entity
// =============================================================================
public class CardInput : BaseEntity
{
    [Required]
    [MaxLength(50)]
    public string Kind { get; set; } = string.Empty; // skill_resource, artifact, etc.

    [MaxLength(500)]
    public string? Path { get; set; }

    [MaxLength(1000)]
    public string? Description { get; set; }

    public Guid CardId { get; set; }

    [ForeignKey(nameof(CardId))]
    public Card Card { get; set; } = null!;
}

// =============================================================================
// LLM Run Entity (Audit Log)
// =============================================================================
public class LlmRun : BaseEntity
{
    [Required]
    [MaxLength(50)]
    public string PromptName { get; set; } = string.Empty;

    public LlmProvider Provider { get; set; }

    [MaxLength(50)]
    public string Model { get; set; } = string.Empty;

    public int InputTokens { get; set; }
    public int OutputTokens { get; set; }

    [Column(TypeName = "decimal(10,6)")]
    public decimal? CostUsd { get; set; }

    public TimeSpan? Duration { get; set; }

    [Column(TypeName = "text")]
    public string? Request { get; set; }

    [Column(TypeName = "text")]
    public string? Response { get; set; }

    public Guid? ProjectId { get; set; }

    [ForeignKey(nameof(ProjectId))]
    public Project? Project { get; set; }
}

// =============================================================================
// Export Entity
// =============================================================================
public class Export : BaseEntity
{
    [MaxLength(50)]
    public string Format { get; set; } = "filesystem";

    [Column(TypeName = "text")]
    public string? ManifestJson { get; set; }

    public int TotalSkills { get; set; }
    public int TotalCards { get; set; }
    public int Warnings { get; set; }

    public Guid ProjectId { get; set; }

    [ForeignKey(nameof(ProjectId))]
    public Project Project { get; set; } = null!;
}

// =============================================================================
// Tech Dimension & Item Entities
// =============================================================================
public class TechDimension : BaseEntity
{
    [Required]
    [MaxLength(100)]
    public string Code { get; set; } = string.Empty;

    [Required]
    [MaxLength(200)]
    public string Name { get; set; } = string.Empty;

    public int Order { get; set; }

    public ICollection<TechItem> Items { get; set; } = new List<TechItem>();
}

public class TechItem : BaseEntity
{
    [Required]
    [MaxLength(100)]
    public string Code { get; set; } = string.Empty;

    [Required]
    [MaxLength(200)]
    public string Name { get; set; } = string.Empty;

    [MaxLength(500)]
    public string? Description { get; set; }

    public Guid DimensionId { get; set; }

    [ForeignKey(nameof(DimensionId))]
    public TechDimension Dimension { get; set; } = null!;
}

public class ProjectTechChoice : BaseEntity
{
    public Guid ProjectId { get; set; }
    public Guid TechItemId { get; set; }

    [MaxLength(500)]
    public string? Notes { get; set; }

    [ForeignKey(nameof(ProjectId))]
    public Project Project { get; set; } = null!;

    [ForeignKey(nameof(TechItemId))]
    public TechItem TechItem { get; set; } = null!;
}
