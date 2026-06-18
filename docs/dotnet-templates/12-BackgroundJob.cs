// =============================================================================
// BackgroundJob.cs - Background Jobs using Hangfire
// =============================================================================
// Location: AgentsWorkshop.Infrastructure/Jobs/
// Mirrors: Python Dramatiq workers (jobs/)
// =============================================================================

using Microsoft.Extensions.Logging;
using Hangfire;
using AgentsWorkshop.Core.Interfaces;
using AgentsWorkshop.Domain.Entities;
using AgentsWorkshop.Domain.Enums;

namespace AgentsWorkshop.Infrastructure.Jobs;

/// <summary>
/// Background job for artifact text extraction.
/// Equivalent to Python's extract_artifact Dramatiq actor.
/// </summary>
public class ArtifactExtractionJob
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<ArtifactExtractionJob> _logger;

    public ArtifactExtractionJob(IUnitOfWork unitOfWork, ILogger<ArtifactExtractionJob> logger)
    {
        _unitOfWork = unitOfWork;
        _logger = logger;
    }

    /// <summary>
    /// Extract text from an uploaded artifact.
    /// Supports: PDF, DOCX, MD, TXT, CSV, Code files
    /// </summary>
    [AutomaticRetry(Attempts = 3, DelaysInSeconds = new[] { 60, 300, 900 })]
    [Queue("extraction")]
    public async Task ExtractArtifactAsync(Guid artifactId, CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("Starting extraction for artifact {ArtifactId}", artifactId);

        var artifact = await _unitOfWork.Exports
            .Query()
            .Cast<ProjectArtifact>()
            .FirstOrDefaultAsync(a => a.Id == artifactId, cancellationToken);

        if (artifact == null)
        {
            _logger.LogWarning("Artifact {ArtifactId} not found", artifactId);
            return;
        }

        try
        {
            // Update status to extracting
            artifact.ExtractionStatus = ExtractionStatus.Extracting;
            await _unitOfWork.SaveChangesAsync(cancellationToken);

            // Extract based on file type
            var extractedText = await ExtractTextAsync(artifact, cancellationToken);

            // Update artifact with extracted text
            artifact.ExtractedText = extractedText;
            artifact.ExtractionStatus = ExtractionStatus.Extracted;
            artifact.ExtractionError = null;

            await _unitOfWork.SaveChangesAsync(cancellationToken);

            _logger.LogInformation(
                "Successfully extracted {CharCount} characters from artifact {ArtifactId}",
                extractedText?.Length ?? 0,
                artifactId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to extract artifact {ArtifactId}", artifactId);

            artifact.ExtractionStatus = ExtractionStatus.Failed;
            artifact.ExtractionError = ex.Message;

            await _unitOfWork.SaveChangesAsync(cancellationToken);

            throw; // Re-throw for Hangfire retry
        }
    }

    private async Task<string> ExtractTextAsync(ProjectArtifact artifact, CancellationToken cancellationToken)
    {
        var extension = Path.GetExtension(artifact.FileName).ToLowerInvariant();

        return extension switch
        {
            ".pdf" => await ExtractPdfAsync(artifact.FilePath!, cancellationToken),
            ".docx" => await ExtractDocxAsync(artifact.FilePath!, cancellationToken),
            ".md" or ".txt" => await File.ReadAllTextAsync(artifact.FilePath!, cancellationToken),
            ".csv" => await ExtractCsvAsync(artifact.FilePath!, cancellationToken),
            ".cs" or ".py" or ".js" or ".ts" => await ExtractCodeAsync(artifact.FilePath!, cancellationToken),
            _ => throw new NotSupportedException($"File type '{extension}' is not supported for extraction")
        };
    }

    private async Task<string> ExtractPdfAsync(string filePath, CancellationToken cancellationToken)
    {
        // Use a library like iTextSharp, PdfPig, or similar
        // Example with PdfPig:
        // using UglyToad.PdfPig;
        // using var document = PdfDocument.Open(filePath);
        // return string.Join("\n\n", document.GetPages().Select(p => p.Text));

        throw new NotImplementedException("Implement PDF extraction with PdfPig or similar library");
    }

    private async Task<string> ExtractDocxAsync(string filePath, CancellationToken cancellationToken)
    {
        // Use DocumentFormat.OpenXml or similar
        // using DocumentFormat.OpenXml.Packaging;
        // using var doc = WordprocessingDocument.Open(filePath, false);
        // return doc.MainDocumentPart?.Document.Body?.InnerText ?? string.Empty;

        throw new NotImplementedException("Implement DOCX extraction with OpenXml library");
    }

    private async Task<string> ExtractCsvAsync(string filePath, CancellationToken cancellationToken)
    {
        var content = await File.ReadAllTextAsync(filePath, cancellationToken);
        // Optionally parse and format CSV for better readability
        return content;
    }

    private async Task<string> ExtractCodeAsync(string filePath, CancellationToken cancellationToken)
    {
        var content = await File.ReadAllTextAsync(filePath, cancellationToken);
        var fileName = Path.GetFileName(filePath);
        var extension = Path.GetExtension(filePath);

        // Format as code block with language hint
        var language = extension switch
        {
            ".cs" => "csharp",
            ".py" => "python",
            ".js" => "javascript",
            ".ts" => "typescript",
            _ => ""
        };

        return $"```{language}\n// File: {fileName}\n{content}\n```";
    }
}

// =============================================================================
// Export Job
// =============================================================================

public class ExportJob
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly IExportService _exportService;
    private readonly ILogger<ExportJob> _logger;

    public ExportJob(
        IUnitOfWork unitOfWork,
        IExportService exportService,
        ILogger<ExportJob> logger)
    {
        _unitOfWork = unitOfWork;
        _exportService = exportService;
        _logger = logger;
    }

    /// <summary>
    /// Background export job with advisory locking.
    /// </summary>
    [Queue("export")]
    public async Task ExportProjectAsync(Guid projectId, string outputPath, CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("Starting background export for project {ProjectId}", projectId);

        try
        {
            var result = await _exportService.ExportProjectAsync(
                projectId,
                new Contracts.Requests.ExportRequest("filesystem", outputPath),
                cancellationToken);

            _logger.LogInformation(
                "Export completed for project {ProjectId}: {SkillCount} skills, {CardCount} cards",
                projectId,
                result.TotalSkills,
                result.TotalCards);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Export failed for project {ProjectId}", projectId);
            throw;
        }
    }
}

// =============================================================================
// Scheduled Jobs - Recurring Tasks
// =============================================================================

public class ScheduledJobs
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<ScheduledJobs> _logger;

    public ScheduledJobs(IUnitOfWork unitOfWork, ILogger<ScheduledJobs> logger)
    {
        _unitOfWork = unitOfWork;
        _logger = logger;
    }

    /// <summary>
    /// Daily cleanup of old exports (keeps last 10 per project).
    /// </summary>
    [DisableConcurrentExecution(timeoutInSeconds: 600)]
    public async Task CleanupOldExportsAsync()
    {
        _logger.LogInformation("Starting export cleanup job");

        var projects = await _unitOfWork.Projects.GetAllAsync();

        foreach (var project in projects)
        {
            var exports = await _unitOfWork.Exports
                .FindAsync(e => e.ProjectId == project.Id);

            var toDelete = exports
                .OrderByDescending(e => e.CreatedAt)
                .Skip(10)
                .ToList();

            if (toDelete.Any())
            {
                _unitOfWork.Exports.RemoveRange(toDelete);
                _logger.LogInformation(
                    "Removed {Count} old exports from project {ProjectId}",
                    toDelete.Count,
                    project.Id);
            }
        }

        await _unitOfWork.SaveChangesAsync();
    }

    /// <summary>
    /// Hourly retry of failed extractions.
    /// </summary>
    public async Task RetryFailedExtractionsAsync()
    {
        _logger.LogInformation("Checking for failed extractions to retry");

        // Query artifacts with failed extraction (would need to add artifact to repositories)
        // and re-enqueue them
    }
}

// =============================================================================
// Job Registration (in Program.cs or Startup)
// =============================================================================

public static class JobRegistration
{
    public static void RegisterRecurringJobs()
    {
        // Run cleanup daily at 2 AM
        RecurringJob.AddOrUpdate<ScheduledJobs>(
            "cleanup-old-exports",
            job => job.CleanupOldExportsAsync(),
            Cron.Daily(2));

        // Retry failed extractions every hour
        RecurringJob.AddOrUpdate<ScheduledJobs>(
            "retry-failed-extractions",
            job => job.RetryFailedExtractionsAsync(),
            Cron.Hourly);
    }

    public static void EnqueueArtifactExtraction(Guid artifactId)
    {
        BackgroundJob.Enqueue<ArtifactExtractionJob>(
            job => job.ExtractArtifactAsync(artifactId, CancellationToken.None));
    }

    public static void EnqueueProjectExport(Guid projectId, string outputPath)
    {
        BackgroundJob.Enqueue<ExportJob>(
            job => job.ExportProjectAsync(projectId, outputPath, CancellationToken.None));
    }
}
