using Microsoft.EntityFrameworkCore;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;

namespace SmartServe.Api.Services;

/// <summary>Retention configuration. Every field defaults to "disabled"/empty: no eligibility window, status set, or disposal-record lifetime is invented here. Disposal stays fully inert until the approved company policy supplies all three, pending confirmation in docs/decisions/access-request-contract.md (TASK-014).</summary>
public class RetentionOptions
{
    /// <summary>Explicit master switch. Even a non-zero window/status configuration left over from testing cannot trigger disposal unless this is also set true, so enabling retention always requires a deliberate, reviewable change.</summary>
    public bool Enabled { get; set; }

    /// <summary>Days a request must have been in a configured terminal status before it is eligible for disposal. 0 = not configured (no eligibility approved yet).</summary>
    public int TerminalRequestRetentionDays { get; set; }

    /// <summary>Status names eligible for disposal once aged past the window. No default set is assumed — the approved policy must name them explicitly (e.g. "Approved", "Rejected", "Fulfilled").</summary>
    public string[] EligibleTerminalStatuses { get; set; } = Array.Empty<string>();

    /// <summary>Days a minimal disposal record (<see cref="RetentionDisposalRecord"/>) is kept before it, too, may be purged. 0 = no approved lifetime yet, so disposal records are kept rather than guessed-expired.</summary>
    public int DisposalRecordRetentionDays { get; set; }
}

/// <summary>Disposes requests (and their audit history) once they have aged past the configured retention window in a configured terminal status, recording a minimal disposal record that preserves the review-timing facts needed for NFR-003 reporting (see <see cref="RetentionDisposalRecord"/>). Notification records are intentionally left untouched: their retention is a separate decision not covered by the approved policy. (proposed, TASK-014)</summary>
public class RetentionService : BackgroundService
{
    private readonly IDbContextFactory<SmartServeDbContext> _dbFactory;
    private readonly RetentionOptions _options;
    private readonly ILogger<RetentionService> _log;
    private readonly TimeSpan _interval = TimeSpan.FromHours(24);

    public RetentionService(IDbContextFactory<SmartServeDbContext> dbFactory, RetentionOptions options,
        ILogger<RetentionService> log)
    {
        _dbFactory = dbFactory;
        _options = options;
        _log = log;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var disposed = await DisposeEligibleAsync(stoppingToken);
                if (disposed > 0)
                    _log.LogInformation("Retention sweep disposed {Count} terminal requests past the retention window.", disposed);
            }
            catch (Exception ex) when (!stoppingToken.IsCancellationRequested)
            {
                _log.LogError(ex, "Retention disposal sweep failed.");
            }

            try { await Task.Delay(_interval, stoppingToken); } catch (OperationCanceledException) { }
        }
    }

    /// <summary>Can be invoked on demand (startup, tests, or an admin action) in addition to the background loop. No-op unless retention is explicitly enabled with both an approved window and an approved eligible-status set (TASK-014).</summary>
    public async Task<int> DisposeEligibleAsync(CancellationToken ct = default)
    {
        if (!_options.Enabled || _options.TerminalRequestRetentionDays <= 0 || _options.EligibleTerminalStatuses.Length == 0)
            return 0;

        var eligibleStatuses = ParseEligibleStatuses(_options.EligibleTerminalStatuses);
        if (eligibleStatuses.Count == 0)
            return 0; // Configured names didn't resolve to any known status; fail closed rather than guess.

        var cutoff = DateTimeOffset.UtcNow.AddDays(-_options.TerminalRequestRetentionDays);

        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var eligible = await db.PortalRequests
            .Where(r => eligibleStatuses.Contains(r.Status) && (r.UpdatedAt ?? r.CreatedAt) < cutoff)
            .ToListAsync(ct);

        foreach (var request in eligible)
        {
            var audits = await db.RequestAudits
                .Where(a => a.PortalRequestId == request.Id)
                .OrderBy(a => a.Timestamp)
                .ToListAsync(ct);
            // Preserve the "initial review" timestamp (first post-submission change) before the audit trail is deleted,
            // so the NFR-003 metric for this request is unchanged by disposal.
            var firstReviewAt = audits.FirstOrDefault(a => a.OldStatus is not null)?.Timestamp;

            db.RetentionDisposalRecords.Add(new RetentionDisposalRecord
            {
                PortalRequestId = request.Id,
                Kind = request.Kind,
                FinalStatus = request.Status,
                SubmittedAt = request.CreatedAt,
                FirstReviewAt = firstReviewAt
            });
            db.RequestAudits.RemoveRange(audits);
            db.PortalRequests.Remove(request);
        }

        if (eligible.Count > 0)
            await db.SaveChangesAsync(ct);

        if (_options.DisposalRecordRetentionDays > 0)
            await PurgeExpiredDisposalRecordsAsync(db, ct);

        return eligible.Count;
    }

    private async Task PurgeExpiredDisposalRecordsAsync(SmartServeDbContext db, CancellationToken ct)
    {
        var disposalCutoff = DateTimeOffset.UtcNow.AddDays(-_options.DisposalRecordRetentionDays);
        var expired = await db.RetentionDisposalRecords.Where(d => d.DisposedAt < disposalCutoff).ToListAsync(ct);
        if (expired.Count == 0) return;

        db.RetentionDisposalRecords.RemoveRange(expired);
        await db.SaveChangesAsync(ct);
    }

    private static List<RequestStatus> ParseEligibleStatuses(string[] names)
    {
        var statuses = new List<RequestStatus>();
        foreach (var name in names)
        {
            if (Enum.TryParse<RequestStatus>(name, ignoreCase: true, out var status))
                statuses.Add(status);
        }
        return statuses;
    }
}
