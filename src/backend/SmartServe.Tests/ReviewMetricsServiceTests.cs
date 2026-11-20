using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;
using SmartServe.Api.Services;
using SmartServe.Tests.TestSupport;
using Xunit;

namespace SmartServe.Tests;

/// <summary>TASK-013: review-metrics tests against the provisional (proposed) "first status change" / "1 business day, skip weekends" definitions.</summary>
public class ReviewMetricsServiceTests : IAsyncLifetime
{
    private SmartServeWebApplicationFactory _factory = null!;
    private IDbContextFactory<SmartServeDbContext> _dbFactory = null!;
    private Guid _accessTypeId;

    public async Task InitializeAsync()
    {
        _factory = new SmartServeWebApplicationFactory();
        _ = _factory.CreateClient(); // forces host startup
        _dbFactory = _factory.Services.GetRequiredService<IDbContextFactory<SmartServeDbContext>>();

        await using var db = await _dbFactory.CreateDbContextAsync();
        _accessTypeId = (await db.RequestTypes.FirstAsync(t => t.Kind == RequestKind.Access)).Id;
    }

    public Task DisposeAsync()
    {
        _factory.Dispose();
        return Task.CompletedTask;
    }

    private async Task<Guid> SeedRequestAsync(DateTimeOffset submittedAt, DateTimeOffset? firstReviewAt)
    {
        await using var db = await _dbFactory.CreateDbContextAsync();
        var request = new PortalRequest
        {
            Kind = RequestKind.Access,
            RequestTypeId = _accessTypeId,
            Title = "t",
            Description = "d",
            RequesterId = "emp-metrics",
            Status = RequestStatus.Submitted,
            CreatedAt = submittedAt
        };
        db.PortalRequests.Add(request);
        db.RequestAudits.Add(new RequestAudit
        {
            PortalRequestId = request.Id, ActorId = "emp-metrics", OldStatus = null, NewStatus = RequestStatus.Submitted,
            Timestamp = submittedAt
        });
        if (firstReviewAt is not null)
        {
            db.RequestAudits.Add(new RequestAudit
            {
                PortalRequestId = request.Id, ActorId = "mgr-metrics", OldStatus = RequestStatus.Submitted,
                NewStatus = RequestStatus.UnderReview, Timestamp = firstReviewAt.Value
            });
        }
        await db.SaveChangesAsync();
        return request.Id;
    }

    [Fact]
    public async Task Request_reviewed_within_one_business_day_counts_toward_the_target()
    {
        var submitted = new DateTimeOffset(2026, 11, 16, 9, 0, 0, TimeSpan.Zero); // Monday
        await SeedRequestAsync(submitted, submitted.AddHours(5)); // same day, well within target

        var metrics = new ReviewMetricsService(_dbFactory);
        var samples = await metrics.ComputeSamplesAsync();

        var sample = Assert.Single(samples);
        Assert.True(sample.WithinTarget);
    }

    [Fact]
    public async Task Request_reviewed_after_the_business_day_window_does_not_count_toward_the_target()
    {
        var submitted = new DateTimeOffset(2026, 11, 16, 9, 0, 0, TimeSpan.Zero); // Monday
        await SeedRequestAsync(submitted, submitted.AddDays(3)); // Thursday, outside a 1-business-day window

        var metrics = new ReviewMetricsService(_dbFactory);
        var samples = await metrics.ComputeSamplesAsync();

        var sample = Assert.Single(samples);
        Assert.False(sample.WithinTarget);
    }

    [Fact]
    public async Task Weekend_submission_extends_the_target_deadline_to_the_next_business_day()
    {
        var submitted = new DateTimeOffset(2026, 11, 20, 16, 0, 0, TimeSpan.Zero); // Friday
        // Monday same time is exactly 1 business day later (Sat/Sun skipped); request reviewed Monday morning should count.
        await SeedRequestAsync(submitted, new DateTimeOffset(2026, 11, 23, 9, 0, 0, TimeSpan.Zero));

        var metrics = new ReviewMetricsService(_dbFactory);
        var samples = await metrics.ComputeSamplesAsync();

        var sample = Assert.Single(samples);
        Assert.True(sample.WithinTarget);
    }

    [Fact]
    public async Task Unreviewed_request_still_inside_its_window_is_excluded_as_pending()
    {
        var submitted = DateTimeOffset.UtcNow; // Monday 9am style window still open relative to "now" below
        await SeedRequestAsync(submitted, submitted.AddHours(2));
        await SeedRequestAsync(submitted, null); // not yet reviewed, deadline has not passed

        var metrics = new ReviewMetricsService(_dbFactory);
        var summary = await metrics.ComputeSummaryAsync();

        Assert.Equal(2, summary.TotalSubmitted);
        Assert.Equal(1, summary.EligibleForReporting); // only the reviewed one has a judgeable outcome so far
        Assert.Equal(1, summary.ReviewedWithinTarget);
        Assert.Equal(0, summary.OverdueUnreviewed);
        Assert.Equal(100.0, summary.PercentageWithinTarget);
    }

    [Fact]
    public async Task Overdue_unreviewed_request_counts_as_a_miss_against_the_target()
    {
        var submitted = new DateTimeOffset(2026, 11, 16, 9, 0, 0, TimeSpan.Zero); // Monday, deadline Tue 9am
        await SeedRequestAsync(submitted, submitted.AddHours(2)); // reviewed, within target
        await SeedRequestAsync(submitted, null); // never reviewed; deadline is long past "asOf" below

        var metrics = new ReviewMetricsService(_dbFactory);
        var asOf = submitted.AddDays(5); // well past the 1-business-day deadline for both
        var samples = await metrics.ComputeSamplesAsync(asOf);

        Assert.Equal(2, samples.Count(s => s.EligibleForReporting));
        var overdueMiss = Assert.Single(samples, s => s.FirstReviewAt is null);
        Assert.True(overdueMiss.EligibleForReporting);
        Assert.False(overdueMiss.WithinTarget);
    }

    [Fact]
    public async Task Provisional_flag_is_surfaced_on_the_summary()
    {
        var submitted = new DateTimeOffset(2026, 11, 16, 9, 0, 0, TimeSpan.Zero);
        await SeedRequestAsync(submitted, submitted.AddHours(2));

        var metrics = new ReviewMetricsService(_dbFactory);
        var summary = await metrics.ComputeSummaryAsync();

        Assert.True(summary.Provisional);
    }
}
