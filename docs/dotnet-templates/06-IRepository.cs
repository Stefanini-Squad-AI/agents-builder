// =============================================================================
// IRepository.cs - Generic Repository Interface
// =============================================================================
// Location: AgentsWorkshop.Core/Interfaces/IRepository.cs
// =============================================================================

using System.Linq.Expressions;
using AgentsWorkshop.Domain.Entities;

namespace AgentsWorkshop.Core.Interfaces;

/// <summary>
/// Generic repository interface for basic CRUD operations.
/// </summary>
public interface IRepository<TEntity> where TEntity : BaseEntity
{
    // =============================================================================
    // Query Methods
    // =============================================================================
    
    Task<TEntity?> GetByIdAsync(Guid id, CancellationToken cancellationToken = default);
    
    Task<TEntity?> GetByIdAsync(
        Guid id, 
        params Expression<Func<TEntity, object>>[] includes);
    
    Task<IReadOnlyList<TEntity>> GetAllAsync(CancellationToken cancellationToken = default);
    
    Task<IReadOnlyList<TEntity>> FindAsync(
        Expression<Func<TEntity, bool>> predicate,
        CancellationToken cancellationToken = default);
    
    Task<IReadOnlyList<TEntity>> FindAsync(
        Expression<Func<TEntity, bool>> predicate,
        params Expression<Func<TEntity, object>>[] includes);
    
    Task<TEntity?> FirstOrDefaultAsync(
        Expression<Func<TEntity, bool>> predicate,
        CancellationToken cancellationToken = default);
    
    Task<bool> ExistsAsync(
        Expression<Func<TEntity, bool>> predicate,
        CancellationToken cancellationToken = default);
    
    Task<int> CountAsync(
        Expression<Func<TEntity, bool>>? predicate = null,
        CancellationToken cancellationToken = default);

    // =============================================================================
    // Pagination
    // =============================================================================
    
    Task<(IReadOnlyList<TEntity> Items, int Total)> GetPagedAsync(
        int page,
        int pageSize,
        Expression<Func<TEntity, bool>>? predicate = null,
        Expression<Func<TEntity, object>>? orderBy = null,
        bool ascending = true,
        CancellationToken cancellationToken = default);

    // =============================================================================
    // Command Methods
    // =============================================================================
    
    void Add(TEntity entity);
    
    void AddRange(IEnumerable<TEntity> entities);
    
    void Update(TEntity entity);
    
    void Remove(TEntity entity);
    
    void RemoveRange(IEnumerable<TEntity> entities);

    // =============================================================================
    // Raw Query Access (for complex queries)
    // =============================================================================
    
    IQueryable<TEntity> Query();
}

// =============================================================================
// Specialized Repository Interfaces
// =============================================================================

public interface IProjectRepository : IRepository<Project>
{
    Task<Project?> GetBySlugAsync(string slug, CancellationToken cancellationToken = default);
    
    Task<Project?> GetWithFullDetailsAsync(Guid id, CancellationToken cancellationToken = default);
    
    Task<bool> SlugExistsAsync(string slug, Guid? excludeId = null, CancellationToken cancellationToken = default);
    
    Task<IReadOnlyList<Project>> GetByTenantAsync(Guid tenantId, CancellationToken cancellationToken = default);
}

public interface ISkillRepository : IRepository<Skill>
{
    Task<Skill?> GetBySlugAsync(Guid projectId, string slug, CancellationToken cancellationToken = default);
    
    Task<IReadOnlyList<Skill>> GetByProjectAsync(Guid projectId, CancellationToken cancellationToken = default);
    
    Task<Skill?> GetWithResourcesAsync(Guid id, CancellationToken cancellationToken = default);
    
    Task<bool> SlugExistsAsync(Guid projectId, string slug, Guid? excludeId = null, CancellationToken cancellationToken = default);
}

public interface ICardRepository : IRepository<Card>
{
    Task<Card?> GetByCodeAsync(Guid projectId, string code, CancellationToken cancellationToken = default);
    
    Task<IReadOnlyList<Card>> GetByPhaseAsync(Guid phaseId, CancellationToken cancellationToken = default);
    
    Task<IReadOnlyList<Card>> GetByProjectAsync(Guid projectId, CancellationToken cancellationToken = default);
    
    Task<Card?> GetWithFullDetailsAsync(Guid id, CancellationToken cancellationToken = default);
    
    Task<IReadOnlyList<Card>> GetDependenciesAsync(Guid cardId, CancellationToken cancellationToken = default);
    
    Task<IReadOnlyList<Card>> GetDependentsAsync(Guid cardId, CancellationToken cancellationToken = default);
}

public interface IPhaseRepository : IRepository<Phase>
{
    Task<IReadOnlyList<Phase>> GetByProjectWithCardsAsync(Guid projectId, CancellationToken cancellationToken = default);
    
    Task<int> GetNextOrderAsync(Guid projectId, CancellationToken cancellationToken = default);
}

// =============================================================================
// Unit of Work Interface
// =============================================================================

public interface IUnitOfWork : IDisposable
{
    IProjectRepository Projects { get; }
    ISkillRepository Skills { get; }
    ICardRepository Cards { get; }
    IPhaseRepository Phases { get; }
    IRepository<Tenant> Tenants { get; }
    IRepository<User> Users { get; }
    IRepository<LlmRun> LlmRuns { get; }
    IRepository<Export> Exports { get; }
    
    Task<int> SaveChangesAsync(CancellationToken cancellationToken = default);
    
    Task BeginTransactionAsync(CancellationToken cancellationToken = default);
    
    Task CommitTransactionAsync(CancellationToken cancellationToken = default);
    
    Task RollbackTransactionAsync(CancellationToken cancellationToken = default);
}
