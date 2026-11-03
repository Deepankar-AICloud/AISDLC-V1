using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;
using SmartServe.Api.Services;
using SmartServe.Tests.TestSupport;
using Xunit;

namespace SmartServe.Tests;

/// <summary>Proves, against a real relational provider (SQLite, not EF Core's InMemory provider), that a
/// transition's status update and its audit record commit as a single atomic SaveChanges: the losing side of a
/// concurrency race gets neither. The InMemory provider used by <see cref="WorkflowAuditTests"/> does not roll
/// back a whole SaveChanges atomically on a concurrency conflict (a documented InMemory-only limitation), so it
/// cannot verify this; SQLite, like SQL Server, treats each SaveChanges call as one transaction.</summary>
public class RelationalAtomicityTests : IAsyncLifetime
{
    private SqliteConnection _keepAliveConnection = null!;
    private IDbContextFactory<SmartServeDbContext> _dbFactory = null!;
    private Guid _accessTypeId;

    public async Task InitializeAsync()
    {
        // A named, cache=shared in-memory database visible from independent connections (one per DbContext), so two
        // concurrent SaveChanges calls run as two genuinely separate connections/transactions, like SQL Server —
        // unlike sharing one SqliteConnection object, which cannot run two overlapping transactions at once.
        // The keep-alive connection's own lifetime keeps the shared in-memory database from being dropped.
        var connectionString = $"Data Source=file:atomicity-{Guid.NewGuid():N}?mode=memory&cache=shared";
        _keepAliveConnection = new SqliteConnection(connectionString);
        await _keepAliveConnection.OpenAsync();

        var options = new DbContextOptionsBuilder<SmartServeDbContext>().UseSqlite(connectionString).Options;
        await using (var schemaDb = new SmartServeDbContext(options))
            await schemaDb.Database.EnsureCreatedAsync();

        _dbFactory = new SingleConnectionDbContextFactory(options);

        var type = new RequestType { Kind = RequestKind.Access, Name = "Access" };
        _accessTypeId = type.Id;
        await using var seedDb = new SmartServeDbContext(options);
        seedDb.RequestTypes.Add(type);
        await seedDb.SaveChangesAsync();
    }

    public async Task DisposeAsync() => await _keepAliveConnection.DisposeAsync();

    [Fact]
    public async Task Losing_concurrent_decision_rolls_back_its_audit_record_with_its_status_update()
    {
        var directory = new FakeDirectoryService();
        directory.AddUser(new("mgr-atomic", "Manager Atomic", "mgr.atomic@contoso.example"));
        directory.SetManager("emp-atomic", "mgr-atomic");

        var notifications = new NotificationService(_dbFactory, directory, new FakeEmailSender(), NullLogger<NotificationService>.Instance);
        var workflow = new WorkflowService(_dbFactory, directory, notifications);

        var request = await workflow.SubmitAsync(RequestKind.Access, _accessTypeId, "Atomic", "Atomic test", "emp-atomic");
        Assert.Equal(RequestStatus.UnderReview, request.Status); // manager resolves synchronously on submission

        var arrived = 0;
        var bothArrived = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        workflow.OnBeforeTransitionSave = async _ =>
        {
            if (Interlocked.Increment(ref arrived) == 2) bothArrived.TrySetResult();
            await bothArrived.Task; // both calls must read before either saves, guaranteeing a genuine race
        };

        var t1 = workflow.DecideAsync(request.Id, "mgr-atomic-1", true, "a");
        var t2 = workflow.DecideAsync(request.Id, "mgr-atomic-2", false, "b");

        var outcomes = await Task.WhenAll(t1.ContinueWith(TaskOutcome), t2.ContinueWith(TaskOutcome));
        workflow.OnBeforeTransitionSave = null;

        Assert.Equal(1, outcomes.Count(o => o == "ok"));
        Assert.Equal(1, outcomes.Count(o => o == "conflict"));

        await using var db = await _dbFactory.CreateDbContextAsync();
        var finalRequest = await db.PortalRequests.AsNoTracking().FirstAsync(r => r.Id == request.Id);
        Assert.True(finalRequest.Status is RequestStatus.Approved or RequestStatus.Rejected);

        var decisionAudits = await db.RequestAudits
            .Where(a => a.PortalRequestId == request.Id && a.OldStatus == RequestStatus.UnderReview)
            .ToListAsync();

        // Real relational atomicity: exactly one decision audit record exists for the UnderReview->decision
        // transition — the loser's audit insert rolled back together with its rejected status update, in the
        // same SaveChanges transaction. If the loser's audit had landed independently of its status update,
        // this count would be 2.
        var winningAudit = Assert.Single(decisionAudits);
        Assert.Equal(finalRequest.Status, winningAudit.NewStatus);

        static string TaskOutcome(Task<PortalRequest> t)
        {
            if (t.IsCompletedSuccessfully) return "ok";
            if (t.Exception?.GetBaseException() is ConcurrentTransitionException) return "conflict";
            throw t.Exception!.GetBaseException();
        }
    }

    [Fact]
    public async Task Notification_finalize_persistence_failure_reports_failed_not_the_unpersisted_computed_outcome()
    {
        var directory = new FakeDirectoryService();
        directory.AddUser(new("svc-finalize-fail", "Service FinalizeFail", "svc.finalizefail@contoso.example"));

        var emailSender = new FakeEmailSender(); // would otherwise report Accepted
        var notifications = new NotificationService(_dbFactory, directory, emailSender, NullLogger<NotificationService>.Instance);

        // Force FinalizeAsync's own SaveChangesAsync to fail for a reason other than a concurrency conflict,
        // simulating a genuine persistence failure (e.g. a transient connection error) after the outcome was computed.
        notifications.OnBeforeFinalizeSave = _ => throw new InvalidOperationException("Simulated persistence failure");

        var requestId = Guid.NewGuid();
        await using (var seedDb = await _dbFactory.CreateDbContextAsync())
        {
            seedDb.PortalRequests.Add(new PortalRequest
            {
                Id = requestId, Kind = RequestKind.Service, RequestTypeId = _accessTypeId,
                Title = "x", Description = "y", RequesterId = "svc-finalize-fail", Status = RequestStatus.Submitted
            });
            await seedDb.SaveChangesAsync();
        }

        var record = await notifications.SendAsync(requestId, "Requester", NotificationTemplate.RequesterSubmitted, "svc-finalize-fail");

        // The email was "Accepted" in-memory, but persisting that outcome failed — the caller must see Failed, not Accepted.
        Assert.Equal(NotificationStatus.Failed, record.Status);
        Assert.Contains("FinalizePersistFailed", record.Reason);
    }

    /// <summary>Hands out a new DbContext per call, all sharing the one open SQLite connection above.</summary>
    private sealed class SingleConnectionDbContextFactory : IDbContextFactory<SmartServeDbContext>
    {
        private readonly DbContextOptions<SmartServeDbContext> _options;
        public SingleConnectionDbContextFactory(DbContextOptions<SmartServeDbContext> options) => _options = options;
        public SmartServeDbContext CreateDbContext() => new(_options);
        public Task<SmartServeDbContext> CreateDbContextAsync(CancellationToken ct = default) => Task.FromResult(CreateDbContext());
    }
}
