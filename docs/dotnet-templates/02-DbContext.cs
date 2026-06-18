// =============================================================================
// ApplicationDbContext.cs - Entity Framework Core DbContext
// =============================================================================
// Location: AgentsWorkshop.Infrastructure/Data/ApplicationDbContext.cs
// =============================================================================

using Microsoft.EntityFrameworkCore;
using AgentsWorkshop.Domain.Entities;

namespace AgentsWorkshop.Infrastructure.Data;

public class ApplicationDbContext : DbContext
{
    public ApplicationDbContext(DbContextOptions<ApplicationDbContext> options)
        : base(options)
    {
    }

    // =============================================================================
    // DbSets - Maps to database tables
    // =============================================================================
    public DbSet<User> Users => Set<User>();
    public DbSet<Tenant> Tenants => Set<Tenant>();
    public DbSet<Project> Projects => Set<Project>();
    public DbSet<ProjectArtifact> ProjectArtifacts => Set<ProjectArtifact>();
    public DbSet<ProjectQaAnswer> ProjectQaAnswers => Set<ProjectQaAnswer>();
    public DbSet<ProjectTechChoice> ProjectTechChoices => Set<ProjectTechChoice>();
    public DbSet<TechDimension> TechDimensions => Set<TechDimension>();
    public DbSet<TechItem> TechItems => Set<TechItem>();
    public DbSet<Skill> Skills => Set<Skill>();
    public DbSet<SkillResource> SkillResources => Set<SkillResource>();
    public DbSet<Phase> Phases => Set<Phase>();
    public DbSet<Card> Cards => Set<Card>();
    public DbSet<CardSkill> CardSkills => Set<CardSkill>();
    public DbSet<CardDependency> CardDependencies => Set<CardDependency>();
    public DbSet<CardInput> CardInputs => Set<CardInput>();
    public DbSet<LlmRun> LlmRuns => Set<LlmRun>();
    public DbSet<Export> Exports => Set<Export>();

    // =============================================================================
    // Model Configuration
    // =============================================================================
    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        // Apply all configurations from assembly
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(ApplicationDbContext).Assembly);

        // Global query filter for soft delete (if using)
        // modelBuilder.Entity<BaseEntity>().HasQueryFilter(e => !e.IsDeleted);

        // =============================================================================
        // Project Configuration
        // =============================================================================
        modelBuilder.Entity<Project>(entity =>
        {
            entity.ToTable("projects");
            
            entity.HasIndex(e => e.Slug).IsUnique();
            
            entity.Property(e => e.Status)
                .HasConversion<string>()
                .HasMaxLength(20);
            
            entity.HasOne(e => e.Tenant)
                .WithMany(t => t.Projects)
                .HasForeignKey(e => e.TenantId)
                .OnDelete(DeleteBehavior.Restrict);
        });

        // =============================================================================
        // Skill Configuration
        // =============================================================================
        modelBuilder.Entity<Skill>(entity =>
        {
            entity.ToTable("skills");
            
            entity.HasIndex(e => new { e.ProjectId, e.Slug }).IsUnique();
            
            entity.Property(e => e.Kind)
                .HasConversion<string>()
                .HasMaxLength(20);
                
            entity.HasOne(e => e.Project)
                .WithMany(p => p.Skills)
                .HasForeignKey(e => e.ProjectId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        // =============================================================================
        // Card Configuration
        // =============================================================================
        modelBuilder.Entity<Card>(entity =>
        {
            entity.ToTable("cards");
            
            entity.HasIndex(e => new { e.ProjectId, e.Code }).IsUnique();
            
            entity.Property(e => e.Type)
                .HasConversion<string>()
                .HasMaxLength(20);
                
            entity.HasOne(e => e.Phase)
                .WithMany(p => p.Cards)
                .HasForeignKey(e => e.PhaseId)
                .OnDelete(DeleteBehavior.Cascade);
                
            // Check constraint: human_gate requires checklist
            entity.HasCheckConstraint(
                "CK_Card_HumanGateChecklist",
                "human_gate = false OR human_gate_checklist_md IS NOT NULL");
        });

        // =============================================================================
        // Card Dependencies (Self-referencing many-to-many)
        // =============================================================================
        modelBuilder.Entity<CardDependency>(entity =>
        {
            entity.ToTable("card_deps");
            
            entity.HasKey(e => new { e.CardId, e.DependsOnCardId });
            
            entity.HasOne(e => e.Card)
                .WithMany(c => c.Dependencies)
                .HasForeignKey(e => e.CardId)
                .OnDelete(DeleteBehavior.Cascade);
                
            entity.HasOne(e => e.DependsOnCard)
                .WithMany()
                .HasForeignKey(e => e.DependsOnCardId)
                .OnDelete(DeleteBehavior.Restrict);
        });

        // =============================================================================
        // Card-Skill Many-to-Many
        // =============================================================================
        modelBuilder.Entity<CardSkill>(entity =>
        {
            entity.ToTable("card_skills");
            
            entity.HasKey(e => new { e.CardId, e.SkillId });
            
            entity.HasOne(e => e.Card)
                .WithMany(c => c.CardSkills)
                .HasForeignKey(e => e.CardId)
                .OnDelete(DeleteBehavior.Cascade);
                
            entity.HasOne(e => e.Skill)
                .WithMany(s => s.CardSkills)
                .HasForeignKey(e => e.SkillId)
                .OnDelete(DeleteBehavior.Cascade);
        });
    }

    // =============================================================================
    // Automatic Timestamps
    // =============================================================================
    public override Task<int> SaveChangesAsync(CancellationToken cancellationToken = default)
    {
        var entries = ChangeTracker.Entries<BaseEntity>();
        var now = DateTime.UtcNow;

        foreach (var entry in entries)
        {
            if (entry.State == EntityState.Added)
            {
                entry.Entity.CreatedAt = now;
                entry.Entity.UpdatedAt = now;
            }
            else if (entry.State == EntityState.Modified)
            {
                entry.Entity.UpdatedAt = now;
            }
        }

        return base.SaveChangesAsync(cancellationToken);
    }
}
