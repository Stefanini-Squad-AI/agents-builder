// =============================================================================
// Repository.cs - Generic Repository Implementation
// =============================================================================
// Location: AgentsWorkshop.Infrastructure/Repositories/Repository.cs
// =============================================================================

using System.Linq.Expressions;
using Microsoft.EntityFrameworkCore;
using AgentsWorkshop.Core.Interfaces;
using AgentsWorkshop.Domain.Entities;
using AgentsWorkshop.Infrastructure.Data;

namespace AgentsWorkshop.Infrastructure.Repositories;

/// <summary>
/// Generic repository implementation using Entity Framework Core.
/// </summary>
public class Repository<TEntity> : IRepository<TEntity> where TEntity : BaseEntity
{
    protected readonly ApplicationDbContext Context;
    protected readonly DbSet<TEntity> DbSet;

    public Repository(ApplicationDbContext context)
    {
        Context = context;
        DbSet = context.Set<TEntity>();
    }

    // =============================================================================
    // Query Methods
    // =============================================================================

    public virtual async Task<TEntity?> GetByIdAsync(Guid id, CancellationToken cancellationToken = default)
    {
        return await DbSet.FindAsync(new object[] { id }, cancellationToken);
    }

    public virtual async Task<TEntity?> GetByIdAsync(
        Guid id,
        params Expression<Func<TEntity, object>>[] includes)
    {
        IQueryable<TEntity> query = DbSet;

        foreach (var include in includes)
        {
            query = query.Include(include);
        }

        return await query.FirstOrDefaultAsync(e => e.Id == id);
    }

    public virtual async Task<IReadOnlyList<TEntity>> GetAllAsync(CancellationToken cancellationToken = default)
    {
        return await DbSet.ToListAsync(cancellationToken);
    }

    public virtual async Task<IReadOnlyList<TEntity>> FindAsync(
        Expression<Func<TEntity, bool>> predicate,
        CancellationToken cancellationToken = default)
    {
        return await DbSet.Where(predicate).ToListAsync(cancellationToken);
    }

    public virtual async Task<IReadOnlyList<TEntity>> FindAsync(
        Expression<Func<TEntity, bool>> predicate,
        params Expression<Func<TEntity, object>>[] includes)
    {
        IQueryable<TEntity> query = DbSet.Where(predicate);

        foreach (var include in includes)
        {
            query = query.Include(include);
        }

        return await query.ToListAsync();
    }

    public virtual async Task<TEntity?> FirstOrDefaultAsync(
        Expression<Func<TEntity, bool>> predicate,
        CancellationToken cancellationToken = default)
    {
        return await DbSet.FirstOrDefaultAsync(predicate, cancellationToken);
    }

    public virtual async Task<bool> ExistsAsync(
        Expression<Func<TEntity, bool>> predicate,
        CancellationToken cancellationToken = default)
    {
        return await DbSet.AnyAsync(predicate, cancellationToken);
    }

    public virtual async Task<int> CountAsync(
        Expression<Func<TEntity, bool>>? predicate = null,
        CancellationToken cancellationToken = default)
    {
        return predicate == null
            ? await DbSet.CountAsync(cancellationToken)
            : await DbSet.CountAsync(predicate, cancellationToken);
    }

    // =============================================================================
    // Pagination
    // =============================================================================

    public virtual async Task<(IReadOnlyList<TEntity> Items, int Total)> GetPagedAsync(
        int page,
        int pageSize,
        Expression<Func<TEntity, bool>>? predicate = null,
        Expression<Func<TEntity, object>>? orderBy = null,
        bool ascending = true,
        CancellationToken cancellationToken = default)
    {
        IQueryable<TEntity> query = DbSet;

        if (predicate != null)
        {
            query = query.Where(predicate);
        }

        var total = await query.CountAsync(cancellationToken);

        if (orderBy != null)
        {
            query = ascending
                ? query.OrderBy(orderBy)
                : query.OrderByDescending(orderBy);
        }
        else
        {
            query = query.OrderBy(e => e.CreatedAt);
        }

        var items = await query
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync(cancellationToken);

        return (items, total);
    }

    // =============================================================================
    // Command Methods
    // =============================================================================

    public virtual void Add(TEntity entity)
    {
        DbSet.Add(entity);
    }

    public virtual void AddRange(IEnumerable<TEntity> entities)
    {
        DbSet.AddRange(entities);
    }

    public virtual void Update(TEntity entity)
    {
        DbSet.Update(entity);
    }

    public virtual void Remove(TEntity entity)
    {
        DbSet.Remove(entity);
    }

    public virtual void RemoveRange(IEnumerable<TEntity> entities)
    {
        DbSet.RemoveRange(entities);
    }

    // =============================================================================
    // Raw Query Access
    // =============================================================================

    public IQueryable<TEntity> Query() => DbSet.AsQueryable();
}

// =============================================================================
// ProjectRepository Implementation
// =============================================================================

public class ProjectRepository : Repository<Project>, IProjectRepository
{
    public ProjectRepository(ApplicationDbContext context) : base(context) { }

    public async Task<Project?> GetBySlugAsync(string slug, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .FirstOrDefaultAsync(p => p.Slug == slug, cancellationToken);
    }

    public async Task<Project?> GetWithFullDetailsAsync(Guid id, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Include(p => p.QaAnswers)
            .Include(p => p.TechChoices)
                .ThenInclude(tc => tc.TechItem)
                    .ThenInclude(ti => ti.Dimension)
            .Include(p => p.Skills)
                .ThenInclude(s => s.Resources)
            .Include(p => p.Phases)
                .ThenInclude(ph => ph.Cards)
                    .ThenInclude(c => c.CardSkills)
                        .ThenInclude(cs => cs.Skill)
            .Include(p => p.Phases)
                .ThenInclude(ph => ph.Cards)
                    .ThenInclude(c => c.Dependencies)
            .AsSplitQuery()
            .FirstOrDefaultAsync(p => p.Id == id, cancellationToken);
    }

    public async Task<bool> SlugExistsAsync(string slug, Guid? excludeId = null, CancellationToken cancellationToken = default)
    {
        var query = DbSet.Where(p => p.Slug == slug);
        
        if (excludeId.HasValue)
        {
            query = query.Where(p => p.Id != excludeId.Value);
        }

        return await query.AnyAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<Project>> GetByTenantAsync(Guid tenantId, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Where(p => p.TenantId == tenantId)
            .OrderByDescending(p => p.UpdatedAt)
            .ToListAsync(cancellationToken);
    }
}

// =============================================================================
// SkillRepository Implementation
// =============================================================================

public class SkillRepository : Repository<Skill>, ISkillRepository
{
    public SkillRepository(ApplicationDbContext context) : base(context) { }

    public async Task<Skill?> GetBySlugAsync(Guid projectId, string slug, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .FirstOrDefaultAsync(s => s.ProjectId == projectId && s.Slug == slug, cancellationToken);
    }

    public async Task<IReadOnlyList<Skill>> GetByProjectAsync(Guid projectId, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Where(s => s.ProjectId == projectId)
            .Include(s => s.Resources)
            .OrderBy(s => s.Name)
            .ToListAsync(cancellationToken);
    }

    public async Task<Skill?> GetWithResourcesAsync(Guid id, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Include(s => s.Resources)
            .Include(s => s.CardSkills)
                .ThenInclude(cs => cs.Card)
            .FirstOrDefaultAsync(s => s.Id == id, cancellationToken);
    }

    public async Task<bool> SlugExistsAsync(Guid projectId, string slug, Guid? excludeId = null, CancellationToken cancellationToken = default)
    {
        var query = DbSet.Where(s => s.ProjectId == projectId && s.Slug == slug);
        
        if (excludeId.HasValue)
        {
            query = query.Where(s => s.Id != excludeId.Value);
        }

        return await query.AnyAsync(cancellationToken);
    }
}

// =============================================================================
// CardRepository Implementation
// =============================================================================

public class CardRepository : Repository<Card>, ICardRepository
{
    public CardRepository(ApplicationDbContext context) : base(context) { }

    public async Task<Card?> GetByCodeAsync(Guid projectId, string code, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Include(c => c.Phase)
            .FirstOrDefaultAsync(c => c.ProjectId == projectId && c.Code == code, cancellationToken);
    }

    public async Task<IReadOnlyList<Card>> GetByPhaseAsync(Guid phaseId, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Where(c => c.PhaseId == phaseId)
            .Include(c => c.CardSkills)
                .ThenInclude(cs => cs.Skill)
            .OrderBy(c => c.Code)
            .ToListAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<Card>> GetByProjectAsync(Guid projectId, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Where(c => c.ProjectId == projectId)
            .Include(c => c.Phase)
            .Include(c => c.CardSkills)
            .Include(c => c.Dependencies)
            .OrderBy(c => c.Phase.Order)
            .ThenBy(c => c.Code)
            .ToListAsync(cancellationToken);
    }

    public async Task<Card?> GetWithFullDetailsAsync(Guid id, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Include(c => c.Phase)
            .Include(c => c.CardSkills)
                .ThenInclude(cs => cs.Skill)
                    .ThenInclude(s => s.Resources)
            .Include(c => c.Dependencies)
                .ThenInclude(d => d.DependsOnCard)
            .Include(c => c.Inputs)
            .FirstOrDefaultAsync(c => c.Id == id, cancellationToken);
    }

    public async Task<IReadOnlyList<Card>> GetDependenciesAsync(Guid cardId, CancellationToken cancellationToken = default)
    {
        return await Context.CardDependencies
            .Where(d => d.CardId == cardId)
            .Select(d => d.DependsOnCard)
            .ToListAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<Card>> GetDependentsAsync(Guid cardId, CancellationToken cancellationToken = default)
    {
        return await Context.CardDependencies
            .Where(d => d.DependsOnCardId == cardId)
            .Select(d => d.Card)
            .ToListAsync(cancellationToken);
    }
}

// =============================================================================
// UnitOfWork Implementation
// =============================================================================

public class UnitOfWork : IUnitOfWork
{
    private readonly ApplicationDbContext _context;
    private IProjectRepository? _projects;
    private ISkillRepository? _skills;
    private ICardRepository? _cards;
    private IPhaseRepository? _phases;
    private IRepository<Tenant>? _tenants;
    private IRepository<User>? _users;
    private IRepository<LlmRun>? _llmRuns;
    private IRepository<Export>? _exports;

    public UnitOfWork(ApplicationDbContext context)
    {
        _context = context;
    }

    public IProjectRepository Projects => _projects ??= new ProjectRepository(_context);
    public ISkillRepository Skills => _skills ??= new SkillRepository(_context);
    public ICardRepository Cards => _cards ??= new CardRepository(_context);
    public IPhaseRepository Phases => _phases ??= new PhaseRepository(_context);
    public IRepository<Tenant> Tenants => _tenants ??= new Repository<Tenant>(_context);
    public IRepository<User> Users => _users ??= new Repository<User>(_context);
    public IRepository<LlmRun> LlmRuns => _llmRuns ??= new Repository<LlmRun>(_context);
    public IRepository<Export> Exports => _exports ??= new Repository<Export>(_context);

    public async Task<int> SaveChangesAsync(CancellationToken cancellationToken = default)
    {
        return await _context.SaveChangesAsync(cancellationToken);
    }

    public async Task BeginTransactionAsync(CancellationToken cancellationToken = default)
    {
        await _context.Database.BeginTransactionAsync(cancellationToken);
    }

    public async Task CommitTransactionAsync(CancellationToken cancellationToken = default)
    {
        await _context.Database.CommitTransactionAsync(cancellationToken);
    }

    public async Task RollbackTransactionAsync(CancellationToken cancellationToken = default)
    {
        await _context.Database.RollbackTransactionAsync(cancellationToken);
    }

    public void Dispose()
    {
        _context.Dispose();
    }
}

// =============================================================================
// PhaseRepository Implementation
// =============================================================================

public class PhaseRepository : Repository<Phase>, IPhaseRepository
{
    public PhaseRepository(ApplicationDbContext context) : base(context) { }

    public async Task<IReadOnlyList<Phase>> GetByProjectWithCardsAsync(Guid projectId, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Where(p => p.ProjectId == projectId)
            .Include(p => p.Cards)
                .ThenInclude(c => c.CardSkills)
            .OrderBy(p => p.Order)
            .ToListAsync(cancellationToken);
    }

    public async Task<int> GetNextOrderAsync(Guid projectId, CancellationToken cancellationToken = default)
    {
        var maxOrder = await DbSet
            .Where(p => p.ProjectId == projectId)
            .MaxAsync(p => (int?)p.Order, cancellationToken);

        return (maxOrder ?? 0) + 1;
    }
}
