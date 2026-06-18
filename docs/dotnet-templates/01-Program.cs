// =============================================================================
// Program.cs - Application Entry Point
// =============================================================================
// NuGet Packages Required:
// - Microsoft.EntityFrameworkCore.SqlServer (or Npgsql.EntityFrameworkCore.PostgreSQL)
// - Microsoft.AspNetCore.Authentication.JwtBearer
// - Swashbuckle.AspNetCore
// - Serilog.AspNetCore
// - FluentValidation.AspNetCore
// - Hangfire (for background jobs)
// =============================================================================

using Microsoft.EntityFrameworkCore;
using Microsoft.OpenApi.Models;
using Serilog;
using FluentValidation;
using FluentValidation.AspNetCore;
using Hangfire;
using AgentsWorkshop.Infrastructure.Data;
using AgentsWorkshop.Core.Interfaces;
using AgentsWorkshop.Core.Services;
using AgentsWorkshop.Infrastructure.Repositories;

var builder = WebApplication.CreateBuilder(args);

// =============================================================================
// Serilog Configuration
// =============================================================================
Log.Logger = new LoggerConfiguration()
    .ReadFrom.Configuration(builder.Configuration)
    .Enrich.FromLogContext()
    .WriteTo.Console()
    .CreateLogger();

builder.Host.UseSerilog();

// =============================================================================
// Database Configuration
// =============================================================================
builder.Services.AddDbContext<ApplicationDbContext>(options =>
{
    var connectionString = builder.Configuration.GetConnectionString("DefaultConnection");
    
    // PostgreSQL (matching original Python project)
    options.UseNpgsql(connectionString, npgsqlOptions =>
    {
        npgsqlOptions.EnableRetryOnFailure(3);
        npgsqlOptions.CommandTimeout(30);
    });
    
    // For development: enable sensitive data logging
    if (builder.Environment.IsDevelopment())
    {
        options.EnableSensitiveDataLogging();
        options.EnableDetailedErrors();
    }
});

// =============================================================================
// Dependency Injection - Repositories
// =============================================================================
builder.Services.AddScoped(typeof(IRepository<>), typeof(Repository<>));
builder.Services.AddScoped<IProjectRepository, ProjectRepository>();
builder.Services.AddScoped<ISkillRepository, SkillRepository>();
builder.Services.AddScoped<ICardRepository, CardRepository>();
builder.Services.AddScoped<IUnitOfWork, UnitOfWork>();

// =============================================================================
// Dependency Injection - Services
// =============================================================================
builder.Services.AddScoped<IProjectService, ProjectService>();
builder.Services.AddScoped<ISkillService, SkillService>();
builder.Services.AddScoped<IBacklogService, BacklogService>();
builder.Services.AddScoped<IExportService, ExportService>();
builder.Services.AddScoped<IValidationService, ValidationService>();
builder.Services.AddScoped<ILlmService, LlmService>();

// =============================================================================
// FluentValidation
// =============================================================================
builder.Services.AddValidatorsFromAssemblyContaining<Program>();
builder.Services.AddFluentValidationAutoValidation();

// =============================================================================
// Hangfire - Background Jobs (replaces Dramatiq)
// =============================================================================
builder.Services.AddHangfire(config =>
{
    config.UsePostgreSqlStorage(builder.Configuration.GetConnectionString("DefaultConnection"));
});
builder.Services.AddHangfireServer();

// =============================================================================
// Controllers & API Configuration
// =============================================================================
builder.Services.AddControllers()
    .AddJsonOptions(options =>
    {
        options.JsonSerializerOptions.PropertyNamingPolicy = System.Text.Json.JsonNamingPolicy.CamelCase;
        options.JsonSerializerOptions.Converters.Add(new System.Text.Json.Serialization.JsonStringEnumConverter());
    });

builder.Services.AddEndpointsApiExplorer();

// =============================================================================
// Swagger Configuration
// =============================================================================
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new OpenApiInfo
    {
        Title = "Agents Workshop API",
        Version = "v1",
        Description = "API for generating AI agent contracts"
    });
    
    c.AddSecurityDefinition("Bearer", new OpenApiSecurityScheme
    {
        Description = "JWT Authorization header using the Bearer scheme",
        Name = "Authorization",
        In = ParameterLocation.Header,
        Type = SecuritySchemeType.ApiKey,
        Scheme = "Bearer"
    });
});

// =============================================================================
// CORS Configuration
// =============================================================================
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowFrontend", policy =>
    {
        policy.WithOrigins(
                builder.Configuration.GetSection("Cors:Origins").Get<string[]>() 
                ?? new[] { "http://localhost:3000" })
            .AllowAnyMethod()
            .AllowAnyHeader()
            .AllowCredentials();
    });
});

// =============================================================================
// Health Checks
// =============================================================================
builder.Services.AddHealthChecks()
    .AddDbContextCheck<ApplicationDbContext>();

var app = builder.Build();

// =============================================================================
// Middleware Pipeline
// =============================================================================
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseSerilogRequestLogging();
app.UseHttpsRedirection();
app.UseCors("AllowFrontend");
app.UseAuthentication();
app.UseAuthorization();

// Hangfire Dashboard
app.UseHangfireDashboard("/hangfire");

app.MapControllers();
app.MapHealthChecks("/health");

// =============================================================================
// Database Migration on Startup (optional)
// =============================================================================
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
    if (app.Environment.IsDevelopment())
    {
        await db.Database.MigrateAsync();
    }
}

app.Run();
