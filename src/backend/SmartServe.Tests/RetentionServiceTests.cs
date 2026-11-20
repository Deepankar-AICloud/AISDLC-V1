using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging.Abstractions;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;
using SmartServe.Api.Services;
using SmartServe.Tests.TestSupport;
using Xunit;

namespace SmartServe.Tests;

/// <summary>TASK-015: retention eligibility and disposal tests. No schedule is invented: disposal requires an explicit Enabled switch plus an approved window and eligible-status set; disposal never touches notifications; disposed requests keep counting in NFR-003 reporting via the preserved disposal-record timing facts.</summary>
public class RetentionServiceTests : IAsyncLifetime
{
    private SmartServeWebApplicationFactory _factory = null!;
    private IDbContextFactory<SmartServeDbContext> _dbFactory = null!;
    private Guid _accessTypeId;

    public async Task InitializeAsync()
    {
        _factory = new SmartServeWebApplicationFactory();
        _ = _factory.CreateClient();
        _dbFactory = _factory.Services.GetRequiredService<IDbContextFactory<SmartServeDbContext>>();

        await using var db = await _dbFactory.CreateDbContextAsync();
        _accessTypeId = (await db.RequestTypes.FirstAsync(t => t.Kind == RequestKind.Access)).Id;
    }

    public Task DisposeAsync()
    {
        _factory.Dispose();
        return Task.CompletedTask;
    }

    private static RetentionOptions EnabledOptions(int days = 30, int disposalRecordRetentionDays = 0) => new()
    {
        Enabled = true,
        TerminalRequestRetentionDays = days,
        EligibleTerminalStatuses = new[] { "Rejected", "Approved", "Fulfilled" },
        DisposalRecordRetentionDays = disposalRecordRetentionDays
    };

    private async Task<Guid> SeedTerminalRequestAsync(RequestStatus status, DateTimeOffset updatedAt, DateTimeOffset? firstReviewAt = null, DateTimeOffset? createdAt = null)
    {
        await using var db = await _dbFactory.CreateDbContextAsync();
        var request = new PortalRequest
        {
            Kind = RequestKind.Access,
            RequestTypeId = _accessTypeId,
            Title = "t",
            Description = "d",
            RequesterId = "emp-retention",
            Status = status,
            CreatedAt = createdAt ?? updatedAt.AddDays(-1),
            UpdatedAt = updatedAt
        };
        db.PortalRequests.Add(request);
        db.RequestAudits.Add(new RequestAudit
        {
            PortalRequestId = request.Id, ActorId = "emp-retention", OldStatus = null, NewStatus = RequestStatus.Submitted,
            Timestamp = request.CreatedAt
        });
        if (firstReviewAt is not null)
        {
            db.RequestAudits.Add(new RequestAudit
            {
                PortalRequestId = request.Id, ActorId = "mgr-retention", OldStatus = RequestStatus.Submitted,
                NewStatus = status, Timestamp = firstReviewAt.Value
            });
        }
        db.NotificationRecords.Add(new NotificationRecord
        {
            PortalRequestId = request.Id, Template = NotificationTemplate.RequesterSubmitted, RecipientRole = "Requester",
            Status = NotificationStatus.Accepted, CompletedAt = request.CreatedAt
        });
        await db.SaveChangesAsync();
        return request.Id;
    }

    [Fact]
    public async Task Disabled_retention_disposes_nothing_regardless_of_age()
    {
        var oldRequestId = await SeedTerminalRequestAsync(RequestStatus.Fulfilled, DateTimeOffset.UtcNow.AddYears(-10));
        var retention = new RetentionService(_dbFactory, new RetentionOptions { TerminalRequestRetentionDays = 0 },
            NullLogger<RetentionService>.Instance);

        var disposed = await retention.DisposeEligibleAsync();

        Assert.Equal(0, disposed);
        await using var db = await _dbFactory.CreateDbContextAsync();
        Assert.True(await db.PortalRequests.AnyAsync(r => r.Id == oldRequestId));
    }

    [Fact]
    public async Task A_configured_window_without_the_explicit_Enabled_switch_still_disposes_nothing()
    {
        var oldRequestId = await SeedTerminalRequestAsync(RequestStatus.Fulfilled, DateTimeOffset.UtcNow.AddYears(-10));
        var retention = new RetentionService(_dbFactory,
            new RetentionOptions { Enabled = false, TerminalRequestRetentionDays = 30, EligibleTerminalStatuses = new[] { "Fulfilled" } },
            NullLogger<RetentionService>.Instance);

        var disposed = await retention.DisposeEligibleAsync();

        Assert.Equal(0, disposed);
        await using var db = await _dbFactory.CreateDbContextAsync();
        Assert.True(await db.PortalRequests.AnyAsync(r => r.Id == oldRequestId));
    }

    [Fact]
    public async Task Enabled_without_an_approved_eligible_status_set_still_disposes_nothing()
    {
        var oldRequestId = await SeedTerminalRequestAsync(RequestStatus.Fulfilled, DateTimeOffset.UtcNow.AddYears(-10));
        var retention = new RetentionService(_dbFactory,
            new RetentionOptions { Enabled = true, TerminalRequestRetentionDays = 30, EligibleTerminalStatuses = Array.Empty<string>() },
            NullLogger<RetentionService>.Instance);

        var disposed = await retention.DisposeEligibleAsync();

        Assert.Equal(0, disposed);
        await using var db = await _dbFactory.CreateDbContextAsync();
        Assert.True(await db.PortalRequests.AnyAsync(r => r.Id == oldRequestId));
    }

    [Fact]
    public async Task Terminal_request_past_the_configured_window_is_disposed_with_an_auditable_record_but_notifications_are_preserved()
    {
        var oldRequestId = await SeedTerminalRequestAsync(RequestStatus.Rejected, DateTimeOffset.UtcNow.AddDays(-100));
        var recentRequestId = await SeedTerminalRequestAsync(RequestStatus.Approved, DateTimeOffset.UtcNow.AddDays(-1));
        var retention = new RetentionService(_dbFactory, EnabledOptions(), NullLogger<RetentionService>.Instance);

        var disposed = await retention.DisposeEligibleAsync();

        Assert.Equal(1, disposed);
        await using var db = await _dbFactory.CreateDbContextAsync();
        Assert.False(await db.PortalRequests.AnyAsync(r => r.Id == oldRequestId));
        Assert.False(await db.RequestAudits.AnyAsync(a => a.PortalRequestId == oldRequestId));
        Assert.True(await db.PortalRequests.AnyAsync(r => r.Id == recentRequestId)); // not yet eligible, untouched

        // Notification records are a separate, not-yet-approved retention decision: disposal must not delete them.
        Assert.True(await db.NotificationRecords.AnyAsync(n => n.PortalRequestId == oldRequestId));

        var disposalRecord = await db.RetentionDisposalRecords.SingleAsync(r => r.PortalRequestId == oldRequestId);
        Assert.Equal(RequestStatus.Rejected, disposalRecord.FinalStatus);
    }

    [Fact]
    public async Task Non_terminal_request_is_never_disposed_even_when_old()
    {
        var submittedId = await SeedTerminalRequestAsync(RequestStatus.Submitted, DateTimeOffset.UtcNow.AddDays(-100));
        var retention = new RetentionService(_dbFactory, EnabledOptions(), NullLogger<RetentionService>.Instance);

        var disposed = await retention.DisposeEligibleAsync();

        Assert.Equal(0, disposed);
        await using var db = await _dbFactory.CreateDbContextAsync();
        Assert.True(await db.PortalRequests.AnyAsync(r => r.Id == submittedId));
    }

    [Fact]
    public async Task Disposed_request_still_counts_in_review_metrics_reporting()
    {
        var submitted = new DateTimeOffset(2026, 11, 16, 9, 0, 0, TimeSpan.Zero); // Monday
        var firstReview = submitted.AddHours(2); // same day, within target
        var requestId = await SeedTerminalRequestAsync(RequestStatus.Approved, DateTimeOffset.UtcNow.AddDays(-100), firstReview, createdAt: submitted);

        var retention = new RetentionService(_dbFactory, EnabledOptions(days: 1), NullLogger<RetentionService>.Instance);
        var disposed = await retention.DisposeEligibleAsync();
        Assert.Equal(1, disposed);

        await using var db = await _dbFactory.CreateDbContextAsync();
        Assert.False(await db.PortalRequests.AnyAsync(r => r.Id == requestId));

        var metrics = new ReviewMetricsService(_dbFactory);
        var summary = await metrics.ComputeSummaryAsync();

        // The disposed request's timing facts were preserved on the disposal record, so it still contributes
        // to the reporting cohort exactly as it did before disposal.
        Assert.Equal(1, summary.EligibleForReporting);
        Assert.Equal(1, summary.ReviewedWithinTarget);
        Assert.Equal(100.0, summary.PercentageWithinTarget);
    }

    [Fact]
    public async Task Disposal_records_are_kept_until_an_approved_disposal_record_lifetime_is_configured()
    {
        var requestId = await SeedTerminalRequestAsync(RequestStatus.Rejected, DateTimeOffset.UtcNow.AddDays(-400));
        var retention = new RetentionService(_dbFactory, EnabledOptions(), NullLogger<RetentionService>.Instance);
        await retention.DisposeEligibleAsync();

        await using var db = await _dbFactory.CreateDbContextAsync();
        Assert.True(await db.RetentionDisposalRecords.AnyAsync(r => r.PortalRequestId == requestId));

        // A second sweep with no configured disposal-record lifetime (0) must not purge the existing record.
        var disposed = await retention.DisposeEligibleAsync();
        Assert.Equal(0, disposed);
        Assert.True(await db.RetentionDisposalRecords.AnyAsync(r => r.PortalRequestId == requestId));
    }

    [Fact]
    public async Task Disposal_records_are_purged_once_their_approved_lifetime_elapses()
    {
        var requestId = await SeedTerminalRequestAsync(RequestStatus.Rejected, DateTimeOffset.UtcNow.AddDays(-400));
        var retention = new RetentionService(_dbFactory, EnabledOptions(), NullLogger<RetentionService>.Instance);
        await retention.DisposeEligibleAsync();

        await using (var db = await _dbFactory.CreateDbContextAsync())
        {
            var record = await db.RetentionDisposalRecords.SingleAsync(r => r.PortalRequestId == requestId);
            record.DisposedAt = DateTimeOffset.UtcNow.AddDays(-400); // simulate an old disposal record
            await db.SaveChangesAsync();
        }

        var retentionWithExpiry = new RetentionService(_dbFactory, EnabledOptions(disposalRecordRetentionDays: 30),
            NullLogger<RetentionService>.Instance);
        await retentionWithExpiry.DisposeEligibleAsync();

        await using var verifyDb = await _dbFactory.CreateDbContextAsync();
        Assert.False(await verifyDb.RetentionDisposalRecords.AnyAsync(r => r.PortalRequestId == requestId));
    }
}
