using Microsoft.EntityFrameworkCore;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;

namespace SmartServe.Api.Services;

/// <summary>One request's raw submission/first-review timestamps, used to compute the provisional NFR-003 metric. (proposed, TASK-012)</summary>
public record ReviewTimingSample(
    Guid RequestId,
    DateTimeOffset SubmittedAt,
    DateTimeOffset Deadline,
    DateTimeOffset? FirstReviewAt,
    bool EligibleForReporting,
    bool WithinTarget);

/// <summary>Summary of the 90%-within-one-business-day target (PRD-NFR-003). All thresholds and the reporting-cohort definition here are provisional (proposed) pending confirmation of "initial review" and the business calendar — see docs/decisions/access-request-contract.md.
/// Reporting cohort (denominator): a request becomes "eligible for reporting" once it has been reviewed, OR once its one-business-day deadline has passed without review — i.e. once its outcome (pass or fail) can actually be judged. A request still inside its review window and not yet reviewed is excluded (pending, not yet a miss). This means overdue-and-unreviewed requests DO count against the target, as misses; they are never silently excluded.</summary>
public record ReviewMetricsSummary(
    bool Provisional,
    int TotalSubmitted,
    int EligibleForReporting,
    int ReviewedWithinTarget,
    int OverdueUnreviewed,
    double? PercentageWithinTarget,
    DateTimeOffset GeneratedAt);

/// <summary>Computes ARCH-COMP-007 (Review Metrics / Reporting Service) output from raw, already-persisted timestamps (PortalRequest.CreatedAt, RequestAudit.Timestamp). Stores no pre-aggregated metric so the calculation can change once its definition is confirmed.</summary>
public class ReviewMetricsService
{
    private readonly IDbContextFactory<SmartServeDbContext> _dbFactory;

    public ReviewMetricsService(IDbContextFactory<SmartServeDbContext> dbFactory) => _dbFactory = dbFactory;

    public async Task<ReviewMetricsSummary> ComputeSummaryAsync(CancellationToken ct = default)
    {
        var samples = await ComputeSamplesAsync(ct: ct);
        var total = samples.Count;
        var eligible = samples.Where(s => s.EligibleForReporting).ToList();
        var withinTarget = eligible.Count(s => s.WithinTarget);
        var overdueUnreviewed = eligible.Count(s => s.FirstReviewAt is null);
        double? percentage = eligible.Count > 0 ? Math.Round(100.0 * withinTarget / eligible.Count, 2) : null;

        return new ReviewMetricsSummary(
            Provisional: true,
            TotalSubmitted: total,
            EligibleForReporting: eligible.Count,
            ReviewedWithinTarget: withinTarget,
            OverdueUnreviewed: overdueUnreviewed,
            PercentageWithinTarget: percentage,
            GeneratedAt: DateTimeOffset.UtcNow);
    }

    /// <summary>Exposed separately so tests (and future detail reporting) can assert per-request timing without recomputing. <paramref name="asOf"/> lets callers pin "now" for deterministic eligibility checks; defaults to the current time.
    /// Includes disposed requests (via <see cref="RetentionDisposalRecord"/>): their review-timing facts were captured before disposal specifically so this metric is unaffected by later policy-compliant disposal (TASK-014).</summary>
    public async Task<IReadOnlyList<ReviewTimingSample>> ComputeSamplesAsync(DateTimeOffset? asOf = null, CancellationToken ct = default)
    {
        var now = asOf ?? DateTimeOffset.UtcNow;

        await using var db = await _dbFactory.CreateDbContextAsync(ct);

        var requests = await db.PortalRequests.AsNoTracking()
            .Select(r => new { r.Id, SubmittedAt = r.CreatedAt })
            .ToListAsync(ct);

        var firstReviewByRequest = await db.RequestAudits.AsNoTracking()
            .Where(a => a.OldStatus != null) // excludes the initial Submitted row; first subsequent change = "initial review" (proposed)
            .GroupBy(a => a.PortalRequestId)
            .Select(g => new { RequestId = g.Key, FirstReviewAt = g.Min(a => a.Timestamp) })
            .ToDictionaryAsync(x => x.RequestId, x => x.FirstReviewAt, ct);

        var disposed = await db.RetentionDisposalRecords.AsNoTracking()
            .Select(d => new { d.PortalRequestId, SubmittedAt = d.SubmittedAt, FirstReviewAt = d.FirstReviewAt })
            .ToListAsync(ct);

        var samples = new List<ReviewTimingSample>(requests.Count + disposed.Count);

        foreach (var r in requests)
        {
            DateTimeOffset? firstReview = firstReviewByRequest.TryGetValue(r.Id, out var ts) ? ts : null;
            samples.Add(BuildSample(r.Id, r.SubmittedAt, firstReview, now));
        }
        foreach (var d in disposed)
            samples.Add(BuildSample(d.PortalRequestId, d.SubmittedAt, d.FirstReviewAt, now));

        return samples;
    }

    private static ReviewTimingSample BuildSample(Guid id, DateTimeOffset submittedAt, DateTimeOffset? firstReview, DateTimeOffset now)
    {
        var deadline = BusinessDayCalculator.AddBusinessDays(submittedAt, 1);
        var withinTarget = firstReview is not null && firstReview.Value <= deadline;
        // Eligible once an outcome can be judged: already reviewed (pass or fail), or overdue-and-unreviewed (a miss).
        // Still-pending requests inside their window are excluded — they have not yet failed.
        var eligible = firstReview is not null || deadline <= now;
        return new ReviewTimingSample(id, submittedAt, deadline, firstReview, eligible, withinTarget);
    }
}
