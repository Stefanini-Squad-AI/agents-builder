// =============================================================================
// BaseEntity.cs - Base Entity with UUID and Timestamps
// =============================================================================
// Location: AgentsWorkshop.Domain/Entities/BaseEntity.cs
// Mirrors: Python base.py (UuidPkMixin, TimestampsMixin)
// =============================================================================

using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace AgentsWorkshop.Domain.Entities;

/// <summary>
/// Base entity providing UUID primary key and timestamp tracking.
/// Equivalent to Python's UuidPkMixin + TimestampsMixin.
/// </summary>
public abstract class BaseEntity
{
    /// <summary>
    /// UUID primary key. Auto-generated on insert.
    /// </summary>
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public Guid Id { get; set; }

    /// <summary>
    /// Timestamp when entity was created. Set automatically by DbContext.
    /// </summary>
    public DateTime CreatedAt { get; set; }

    /// <summary>
    /// Timestamp when entity was last updated. Set automatically by DbContext.
    /// </summary>
    public DateTime UpdatedAt { get; set; }
}

/// <summary>
/// Entity with soft delete capability.
/// </summary>
public abstract class SoftDeletableEntity : BaseEntity
{
    public bool IsDeleted { get; set; } = false;
    public DateTime? DeletedAt { get; set; }
}

// =============================================================================
// Domain Enums (matching Python enums)
// =============================================================================

namespace AgentsWorkshop.Domain.Enums;

/// <summary>
/// Project lifecycle status.
/// </summary>
public enum ProjectStatus
{
    Draft,
    InProgress,
    Exported,
    Archived
}

/// <summary>
/// Card execution status.
/// </summary>
public enum CardStatus
{
    Draft,
    Ready,
    InProgress,
    Done
}

/// <summary>
/// Skill kinds defining behavior.
/// </summary>
public enum SkillKind
{
    Context,
    Authoring,
    Analyzer,
    Procedure
}

/// <summary>
/// Card types (Jira-style).
/// </summary>
public enum CardType
{
    Task,
    Story,
    Bug,
    Spike,
    Demo
}

/// <summary>
/// Artifact extraction status.
/// </summary>
public enum ExtractionStatus
{
    Pending,
    Extracting,
    Extracted,
    Failed
}

/// <summary>
/// Validation severity levels.
/// </summary>
public enum ValidationSeverity
{
    Error,    // Blocks export
    Warning   // Allowed but flagged
}

/// <summary>
/// Resource file languages.
/// </summary>
public enum ResourceLanguage
{
    Markdown,
    Sql,
    Yaml,
    Python,
    Plain
}

/// <summary>
/// LLM provider options.
/// </summary>
public enum LlmProvider
{
    Anthropic,
    OpenAI,
    Ollama
}
