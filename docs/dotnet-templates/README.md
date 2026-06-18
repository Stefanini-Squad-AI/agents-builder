# .NET Migration Templates

Templates for migrating from Python FastAPI to .NET (compatible with .NET Core 3.1+).

## Folder Structure

```
src/
├── AgentsWorkshop.Api/           # REST API layer
│   ├── Controllers/              # API endpoints
│   ├── Middleware/               # Custom middleware
│   └── Program.cs                # Entry point
├── AgentsWorkshop.Core/          # Business logic
│   ├── Services/                 # Application services
│   ├── Interfaces/               # Abstractions
│   └── Validators/               # Business validation
├── AgentsWorkshop.Domain/        # Domain models
│   ├── Entities/                 # ORM entities
│   ├── Enums/                    # Domain enums
│   └── ValueObjects/             # Value objects
├── AgentsWorkshop.Infrastructure/ # External concerns
│   ├── Data/                     # EF Core DbContext
│   ├── Repositories/             # Repository implementations
│   └── Jobs/                     # Background jobs
└── AgentsWorkshop.Contracts/     # DTOs & API contracts
    ├── Requests/                 # Request DTOs
    ├── Responses/                # Response DTOs
    └── Events/                   # Domain events
```

## Template Files

| File | Description |
|------|-------------|
| `01-Program.cs` | Application entry point |
| `02-DbContext.cs` | Entity Framework Core DbContext |
| `03-BaseEntity.cs` | Base entity with UUID and timestamps |
| `04-ProjectEntity.cs` | Example domain entity |
| `05-ProjectDto.cs` | Request/Response DTOs |
| `06-IRepository.cs` | Generic repository interface |
| `07-Repository.cs` | Repository implementation |
| `08-IProjectService.cs` | Service interface |
| `09-ProjectService.cs` | Service implementation |
| `10-ProjectsController.cs` | REST API controller |
| `11-ValidationService.cs` | Validation logic |
| `12-BackgroundJob.cs` | Background job with Hangfire |
| `13-appsettings.json` | Configuration template |
| `14-Dockerfile` | Docker configuration |

## Migration Mapping

| Python (FastAPI) | .NET Equivalent |
|-----------------|-----------------|
| FastAPI app | ASP.NET Core |
| SQLAlchemy ORM | Entity Framework Core |
| Pydantic models | DTOs + FluentValidation |
| Dramatiq workers | Hangfire / Background Services |
| Alembic migrations | EF Core Migrations |
| pytest | xUnit / NUnit |

## Quick Start

1. Create solution:
   ```bash
   dotnet new sln -n AgentsWorkshop
   dotnet new webapi -n AgentsWorkshop.Api
   dotnet new classlib -n AgentsWorkshop.Core
   dotnet new classlib -n AgentsWorkshop.Domain
   dotnet new classlib -n AgentsWorkshop.Infrastructure
   dotnet new classlib -n AgentsWorkshop.Contracts
   ```

2. Add projects to solution and references
3. Install NuGet packages (see each template for required packages)
