using System.Net.Http.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;
using SmartServe.Api.Dtos;
using SmartServe.Tests.TestSupport;
using Xunit;

namespace SmartServe.Tests;

/// <summary>Covers every transition's audit fields, dispatch-time ordering via independent DB reads, manager-unresolved/retry flow, and notification outcomes.</summary>
public class WorkflowAuditTests : IAsyncLifetime
{
    private SmartServeWebApplicationFactory _factory = null!;
    private HttpClient _client = null!;
    private Guid _accessTypeId;
    private Guid _serviceTypeId;

    public async Task InitializeAsync()
    {
        _factory = new SmartServeWebApplicationFactory();
        _client = _factory.CreateClient();
        await using var db = await DbFactory().CreateDbContextAsync();
        _accessTypeId = (await db.RequestTypes.FirstAsync(t => t.Kind == RequestKind.Access)).Id;
        _serviceTypeId = (await db.RequestTypes.FirstAsync(t => t.Kind == RequestKind.Service)).Id;
    }

    public Task DisposeAsync()
    {
        _factory.Dispose();
        return Task.CompletedTask;
    }

    private IDbContextFactory<SmartServeDbContext> DbFactory() =>
        _factory.Services.GetRequiredService<IDbContextFactory<SmartServeDbContext>>();

    private HttpRequestMessage Req(HttpMethod method, string path, string userId, string role, object? body = null)
    {
        var msg = new HttpRequestMessage(method, path);
        msg.Headers.Add("Authorization", SmartServeWebApplicationFactory.BearerFor(userId, role));
        if (body is not null) msg.Content = JsonContent.Create(body, options: TestJson.Options);
        return msg;
    }

    private async Task<RequestResponse> CreateAsync(RequestKind kind, Guid typeId, string employeeId)
    {
        var res = await _client.SendAsync(Req(HttpMethod.Post, "/api/requests", employeeId, Roles.Employee,
            new CreateRequestDto(kind, typeId, "Title " + employeeId, "Description")));
        res.EnsureSuccessStatusCode();
        return (await res.Content.ReadFromJsonAsync<RequestResponse>(TestJson.Options))!;
    }

    [Fact]
    public async Task Service_request_submission_writes_single_audit_record_with_null_old_status()
    {
        var testStart = DateTimeOffset.UtcNow.AddSeconds(-1); // lower bound: just before the action started
        var req = await CreateAsync(RequestKind.Service, _serviceTypeId, "svc-employee");

        await using var db = await DbFactory().CreateDbContextAsync();
        var audits = await db.RequestAudits.Where(a => a.PortalRequestId == req.Id).ToListAsync();

        var entry = Assert.Single(audits);
        Assert.Equal("svc-employee", entry.ActorId);
        Assert.Null(entry.OldStatus);
        Assert.Equal(RequestStatus.Submitted, entry.NewStatus);
        Assert.True(entry.Timestamp >= testStart, "timestamp must be at/after the action started");
        Assert.True(entry.Timestamp <= DateTimeOffset.UtcNow, "timestamp must not be in the future");
        Assert.Equal(RequestStatus.Submitted, req.Status);
    }

    [Fact]
    public async Task Access_request_full_lifecycle_writes_one_audit_record_per_transition_with_all_fields()
    {
        _factory.Directory.AddUser(new("mgr-full", "Manager Full", "mgr.full@contoso.example"));
        _factory.Directory.AddUser(new("emp-full", "Employee Full", "emp.full@contoso.example"));
        _factory.Directory.SetManager("emp-full", "mgr-full");

        var testStart = DateTimeOffset.UtcNow.AddSeconds(-1); // lower bound: just before the first action started
        var req = await CreateAsync(RequestKind.Access, _accessTypeId, "emp-full");

        // Submitted -> UnderReview happens synchronously as part of submission when the manager resolves.
        await using (var db = await DbFactory().CreateDbContextAsync())
        {
            var afterSubmit = await db.PortalRequests.AsNoTracking().FirstAsync(r => r.Id == req.Id);
            Assert.Equal(RequestStatus.UnderReview, afterSubmit.Status);
        }

        var decide = await _client.SendAsync(Req(HttpMethod.Post, $"/api/requests/{req.Id}/decision", "mgr-full", Roles.Manager,
            new DecisionDto(true, "looks fine")));
        decide.EnsureSuccessStatusCode();

        var fulfil = await _client.SendAsync(Req(HttpMethod.Post, $"/api/requests/{req.Id}/fulfil", "it-admin-full", Roles.ItAdmin));
        fulfil.EnsureSuccessStatusCode();

        await using var finalDb = await DbFactory().CreateDbContextAsync();
        var audits = await finalDb.RequestAudits.Where(a => a.PortalRequestId == req.Id).OrderBy(a => a.Timestamp).ToListAsync();

        Assert.Equal(4, audits.Count);

        Assert.Null(audits[0].OldStatus);
        Assert.Equal(RequestStatus.Submitted, audits[0].NewStatus);
        Assert.Equal("emp-full", audits[0].ActorId);

        Assert.Equal(RequestStatus.Submitted, audits[1].OldStatus);
        Assert.Equal(RequestStatus.UnderReview, audits[1].NewStatus);
        Assert.Equal("emp-full", audits[1].ActorId);

        Assert.Equal(RequestStatus.UnderReview, audits[2].OldStatus);
        Assert.Equal(RequestStatus.Approved, audits[2].NewStatus);
        Assert.Equal("mgr-full", audits[2].ActorId);

        Assert.Equal(RequestStatus.Approved, audits[3].OldStatus);
        Assert.Equal(RequestStatus.Fulfilled, audits[3].NewStatus);
        Assert.Equal("it-admin-full", audits[3].ActorId);

        foreach (var a in audits)
        {
            Assert.True(a.Timestamp >= testStart, "timestamp must be at/after the lifecycle started");
            Assert.True(a.Timestamp <= DateTimeOffset.UtcNow, "timestamp must not be in the future");
        }

        // Every transition's notification(s) resolved to a terminal outcome, never left Pending.
        var notifications = await finalDb.NotificationRecords.Where(n => n.PortalRequestId == req.Id).ToListAsync();
        Assert.DoesNotContain(notifications, n => n.Status == NotificationStatus.Pending);

        var requesterOutcomes = notifications.Where(n => n.RecipientRole == "Requester")
            .ToDictionary(n => n.Template, n => n.Status);
        Assert.Equal(NotificationStatus.Accepted, requesterOutcomes[NotificationTemplate.RequesterSubmitted]);
        Assert.Equal(NotificationStatus.Accepted, requesterOutcomes[NotificationTemplate.RequesterUnderReview]);
        Assert.Equal(NotificationStatus.Accepted, requesterOutcomes[NotificationTemplate.RequesterApproved]);
        Assert.Equal(NotificationStatus.Accepted, requesterOutcomes[NotificationTemplate.RequesterFulfilled]);

        var managerNotification = notifications.Single(n => n.RecipientRole == "Manager");
        Assert.Equal(NotificationTemplate.ManagerWaitingApproval, managerNotification.Template);
        Assert.Equal(NotificationStatus.Accepted, managerNotification.Status);
        Assert.NotNull(managerNotification.CompletedAt);
    }

    [Fact]
    public async Task Rejection_writes_audit_record_with_old_underreview_new_rejected()
    {
        _factory.Directory.AddUser(new("mgr-rej", "Manager Rej", "mgr.rej@contoso.example"));
        _factory.Directory.SetManager("emp-rej", "mgr-rej");

        var req = await CreateAsync(RequestKind.Access, _accessTypeId, "emp-rej");
        var decide = await _client.SendAsync(Req(HttpMethod.Post, $"/api/requests/{req.Id}/decision", "mgr-rej", Roles.Manager,
            new DecisionDto(false, "not needed")));
        decide.EnsureSuccessStatusCode();

        await using var db = await DbFactory().CreateDbContextAsync();
        var rejectAudit = await db.RequestAudits.Where(a => a.PortalRequestId == req.Id)
            .OrderByDescending(a => a.Timestamp).FirstAsync();

        Assert.Equal(RequestStatus.UnderReview, rejectAudit.OldStatus);
        Assert.Equal(RequestStatus.Rejected, rejectAudit.NewStatus);
        Assert.Equal("mgr-rej", rejectAudit.ActorId);
        Assert.True(rejectAudit.Timestamp <= DateTimeOffset.UtcNow);
        Assert.True(rejectAudit.Timestamp > DateTimeOffset.UtcNow.AddMinutes(-5));

        var updated = await db.PortalRequests.AsNoTracking().FirstAsync(r => r.Id == req.Id);
        Assert.Equal(RequestStatus.Rejected, updated.Status);
    }

    [Fact]
    public async Task UnderReview_transition_persists_status_and_audit_before_manager_email_is_dispatched()
    {
        _factory.Directory.AddUser(new("mgr-order", "Manager Order", "mgr.order@contoso.example"));
        _factory.Directory.SetManager("emp-order", "mgr-order");

        RequestStatus? observedStatusDuringSend = null;
        int observedAuditCountDuringSend = -1;

        _factory.EmailSender.OnSend = async message =>
        {
            if (!message.Subject.StartsWith("Approval needed")) return; // only assert for the manager template
            await using var independentDb = await DbFactory().CreateDbContextAsync();
            var persisted = await independentDb.PortalRequests.AsNoTracking()
                .FirstAsync(r => r.RequesterId == "emp-order");
            observedStatusDuringSend = persisted.Status;
            observedAuditCountDuringSend = await independentDb.RequestAudits
                .CountAsync(a => a.PortalRequestId == persisted.Id);
        };

        await CreateAsync(RequestKind.Access, _accessTypeId, "emp-order");

        Assert.Equal(RequestStatus.UnderReview, observedStatusDuringSend);
        Assert.Equal(2, observedAuditCountDuringSend); // Submitted + UnderReview already persisted
    }

    [Fact]
    public async Task Approved_transition_persists_status_before_requester_notification_is_dispatched()
    {
        _factory.Directory.AddUser(new("mgr-appr", "Manager Appr", "mgr.appr@contoso.example"));
        _factory.Directory.AddUser(new("emp-appr", "Employee Appr", "emp.appr@contoso.example"));
        _factory.Directory.SetManager("emp-appr", "mgr-appr");
        var req = await CreateAsync(RequestKind.Access, _accessTypeId, "emp-appr");

        RequestStatus? observed = null;
        _factory.EmailSender.OnSend = async message =>
        {
            if (!message.Subject.Contains("approved")) return;
            await using var independentDb = await DbFactory().CreateDbContextAsync();
            observed = (await independentDb.PortalRequests.AsNoTracking().FirstAsync(r => r.Id == req.Id)).Status;
        };

        var decide = await _client.SendAsync(Req(HttpMethod.Post, $"/api/requests/{req.Id}/decision", "mgr-appr", Roles.Manager,
            new DecisionDto(true, null)));
        decide.EnsureSuccessStatusCode();

        Assert.Equal(RequestStatus.Approved, observed);
    }

    [Fact]
    public async Task Fulfilled_transition_persists_status_before_requester_notification_is_dispatched()
    {
        _factory.Directory.AddUser(new("mgr-fulf", "Manager Fulf", "mgr.fulf@contoso.example"));
        _factory.Directory.AddUser(new("emp-fulf", "Employee Fulf", "emp.fulf@contoso.example"));
        _factory.Directory.SetManager("emp-fulf", "mgr-fulf");
        var req = await CreateAsync(RequestKind.Access, _accessTypeId, "emp-fulf");
        var decide = await _client.SendAsync(Req(HttpMethod.Post, $"/api/requests/{req.Id}/decision", "mgr-fulf", Roles.Manager,
            new DecisionDto(true, null)));
        decide.EnsureSuccessStatusCode();

        RequestStatus? observed = null;
        _factory.EmailSender.OnSend = async message =>
        {
            if (!message.Subject.Contains("fulfilled")) return;
            await using var independentDb = await DbFactory().CreateDbContextAsync();
            observed = (await independentDb.PortalRequests.AsNoTracking().FirstAsync(r => r.Id == req.Id)).Status;
        };

        var fulfil = await _client.SendAsync(Req(HttpMethod.Post, $"/api/requests/{req.Id}/fulfil", "it-admin-fulf", Roles.ItAdmin));
        fulfil.EnsureSuccessStatusCode();

        Assert.Equal(RequestStatus.Fulfilled, observed);
    }

    [Fact]
    public async Task Unresolved_manager_keeps_request_submitted_then_retry_routing_advances_it()
    {
        // No manager registered for this employee at all => ManagerUnresolved (NotSent), not a directory failure.
        var req = await CreateAsync(RequestKind.Access, _accessTypeId, "emp-no-manager");

        await using (var db = await DbFactory().CreateDbContextAsync())
        {
            var afterSubmit = await db.PortalRequests.AsNoTracking().FirstAsync(r => r.Id == req.Id);
            Assert.Equal(RequestStatus.Submitted, afterSubmit.Status);

            var notSent = await db.NotificationRecords.Where(n => n.PortalRequestId == req.Id && n.RecipientRole == "Manager")
                .OrderByDescending(n => n.CreatedAt).FirstAsync();
            Assert.Equal(NotificationStatus.NotSent, notSent.Status);
            Assert.Equal("ManagerUnresolved", notSent.Reason);
        }

        // Now the manager becomes resolvable; an IT admin retries routing.
        _factory.Directory.AddUser(new("mgr-late", "Manager Late", "mgr.late@contoso.example"));
        _factory.Directory.SetManager("emp-no-manager", "mgr-late");

        var retry = await _client.SendAsync(Req(HttpMethod.Post, $"/api/requests/{req.Id}/retry-routing", "it-admin-retry", Roles.ItAdmin));
        retry.EnsureSuccessStatusCode();

        await using var afterRetryDb = await DbFactory().CreateDbContextAsync();
        var afterRetry = await afterRetryDb.PortalRequests.AsNoTracking().FirstAsync(r => r.Id == req.Id);
        Assert.Equal(RequestStatus.UnderReview, afterRetry.Status);

        var routingAudit = await afterRetryDb.RequestAudits.Where(a => a.PortalRequestId == req.Id)
            .OrderByDescending(a => a.Timestamp).FirstAsync();
        Assert.Equal(RequestStatus.Submitted, routingAudit.OldStatus);
        Assert.Equal(RequestStatus.UnderReview, routingAudit.NewStatus);
        Assert.Equal("it-admin-retry", routingAudit.ActorId);
        Assert.True(routingAudit.Timestamp <= DateTimeOffset.UtcNow);
        Assert.True(routingAudit.Timestamp > DateTimeOffset.UtcNow.AddMinutes(-5));
    }

    [Fact]
    public async Task Directory_outage_resolving_manager_is_recorded_as_failed_not_notsent()
    {
        _factory.Directory.MarkBroken("emp-broken-directory");
        var req = await CreateAsync(RequestKind.Access, _accessTypeId, "emp-broken-directory");

        await using var db = await DbFactory().CreateDbContextAsync();
        var afterSubmit = await db.PortalRequests.AsNoTracking().FirstAsync(r => r.Id == req.Id);
        Assert.Equal(RequestStatus.Submitted, afterSubmit.Status); // unchanged — not merely unresolved, a real failure

        var notification = await db.NotificationRecords.Where(n => n.PortalRequestId == req.Id && n.RecipientRole == "Manager")
            .OrderByDescending(n => n.CreatedAt).FirstAsync();
        Assert.Equal(NotificationStatus.Failed, notification.Status);
        Assert.Contains("DirectoryUnavailable", notification.Reason);
    }

    [Fact]
    public async Task Invalid_recipient_email_format_is_recorded_as_notsent()
    {
        // Resolvable manager but with an invalid email address -> NotSent (validation), not Failed.
        _factory.Directory.AddUser(new("mgr-badmail", "Manager BadMail", "not-an-email"));
        _factory.Directory.SetManager("emp-badmail", "mgr-badmail");
        var req = await CreateAsync(RequestKind.Access, _accessTypeId, "emp-badmail");

        await using var db = await DbFactory().CreateDbContextAsync();
        var managerNotification = await db.NotificationRecords
            .Where(n => n.PortalRequestId == req.Id && n.RecipientRole == "Manager" && n.Reason == "InvalidEmailAddress")
            .FirstOrDefaultAsync();
        Assert.NotNull(managerNotification);
        Assert.Equal(NotificationStatus.NotSent, managerNotification!.Status);
    }

    [Fact]
    public async Task Directory_outage_resolving_requesters_own_profile_is_recorded_as_failed_not_notsent()
    {
        // Distinct from ManagerUnresolved/InvalidEmailAddress: a genuine directory failure resolving the requester's own profile.
        _factory.Directory.MarkBroken("emp-requester-outage");
        var req = await CreateAsync(RequestKind.Service, _serviceTypeId, "emp-requester-outage");

        await using var db = await DbFactory().CreateDbContextAsync();
        var requesterNotification = await db.NotificationRecords
            .Where(n => n.PortalRequestId == req.Id && n.RecipientRole == "Requester")
            .OrderByDescending(n => n.CreatedAt).FirstAsync();

        Assert.Equal(NotificationStatus.Failed, requesterNotification.Status);
        Assert.Contains("DirectoryUnavailable", requesterNotification.Reason);
    }

    [Fact]
    public async Task Successful_email_send_is_recorded_as_accepted_with_a_reason()
    {
        _factory.Directory.AddUser(new("svc-accepted", "Service Accepted", "svc.accepted@contoso.example"));
        var req = await CreateAsync(RequestKind.Service, _serviceTypeId, "svc-accepted");

        await using var db = await DbFactory().CreateDbContextAsync();
        var requesterNotification = await db.NotificationRecords
            .Where(n => n.PortalRequestId == req.Id && n.RecipientRole == "Requester")
            .OrderByDescending(n => n.CreatedAt).FirstAsync();

        Assert.Equal(NotificationStatus.Accepted, requesterNotification.Status);
        Assert.False(string.IsNullOrWhiteSpace(requesterNotification.Reason));
    }

    [Fact]
    public async Task Rejection_records_an_accepted_requester_notification()
    {
        _factory.Directory.AddUser(new("mgr-rej-notif", "Manager RejNotif", "mgr.rejnotif@contoso.example"));
        _factory.Directory.AddUser(new("emp-rej-notif", "Employee RejNotif", "emp.rejnotif@contoso.example"));
        _factory.Directory.SetManager("emp-rej-notif", "mgr-rej-notif");

        var req = await CreateAsync(RequestKind.Access, _accessTypeId, "emp-rej-notif");
        var decide = await _client.SendAsync(Req(HttpMethod.Post, $"/api/requests/{req.Id}/decision", "mgr-rej-notif", Roles.Manager,
            new DecisionDto(false, "not needed")));
        decide.EnsureSuccessStatusCode();

        await using var db = await DbFactory().CreateDbContextAsync();
        var rejectedNotification = await db.NotificationRecords
            .Where(n => n.PortalRequestId == req.Id && n.Template == NotificationTemplate.RequesterRejected)
            .OrderByDescending(n => n.CreatedAt).FirstAsync();

        Assert.Equal(NotificationStatus.Accepted, rejectedNotification.Status);
    }

    [Fact]
    public async Task Notification_reconciliation_marks_stale_pending_as_failed_without_touching_fresh_ones()
    {
        await using var db = await DbFactory().CreateDbContextAsync();
        var requestId = Guid.NewGuid();
        db.PortalRequests.Add(new PortalRequest
        {
            Id = requestId, Kind = RequestKind.Access, RequestTypeId = _accessTypeId,
            Title = "x", Description = "y", RequesterId = "someone", Status = RequestStatus.Submitted
        });
        db.NotificationRecords.Add(new NotificationRecord
        {
            PortalRequestId = requestId, RecipientRole = "Requester", Template = NotificationTemplate.RequesterSubmitted,
            Status = NotificationStatus.Pending, LeaseExpiresAt = DateTimeOffset.UtcNow.AddMinutes(-1)
        });
        var freshId = Guid.NewGuid();
        db.NotificationRecords.Add(new NotificationRecord
        {
            Id = freshId, PortalRequestId = requestId, RecipientRole = "Requester",
            Template = NotificationTemplate.RequesterSubmitted, Status = NotificationStatus.Pending,
            LeaseExpiresAt = DateTimeOffset.UtcNow.AddMinutes(15)
        });
        await db.SaveChangesAsync();

        var reconciler = _factory.Services.GetRequiredService<SmartServe.Api.Services.NotificationReconciliationService>();
        var reconciled = await reconciler.ReconcileAsync();
        Assert.Equal(1, reconciled);

        await using var verifyDb = await DbFactory().CreateDbContextAsync();
        var fresh = await verifyDb.NotificationRecords.FirstAsync(n => n.Id == freshId);
        Assert.Equal(NotificationStatus.Pending, fresh.Status); // untouched — lease not yet expired
    }

    [Fact]
    public async Task Concurrent_decisions_on_same_underreview_request_produce_exactly_one_transition_and_notification()
    {
        _factory.Directory.AddUser(new("mgr-race", "Manager Race", "mgr.race@contoso.example"));
        _factory.Directory.SetManager("emp-race", "mgr-race");
        var req = await CreateAsync(RequestKind.Access, _accessTypeId, "emp-race");

        var workflow = _factory.Services.GetRequiredService<SmartServe.Api.Services.WorkflowService>();
        var arrived = 0;
        var bothArrived = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        workflow.OnBeforeTransitionSave = async _ =>
        {
            if (Interlocked.Increment(ref arrived) == 2) bothArrived.TrySetResult();
            await bothArrived.Task; // both calls must read before either saves, guaranteeing a genuine race
        };

        var t1 = workflow.DecideAsync(req.Id, "mgr-race-1", true, "a");
        var t2 = workflow.DecideAsync(req.Id, "mgr-race-2", false, "b");

        var results = await Task.WhenAll(t1.ContinueWith(TaskOutcome), t2.ContinueWith(TaskOutcome));
        workflow.OnBeforeTransitionSave = null;

        Assert.Equal(1, results.Count(r => r == "ok"));
        Assert.Equal(1, results.Count(r => r == "conflict"));

        await using var db = await DbFactory().CreateDbContextAsync();
        var finalRequest = await db.PortalRequests.AsNoTracking().FirstAsync(r => r.Id == req.Id);
        // Final status is whichever call actually won the race (either Approved or Rejected), never left UnderReview.
        Assert.True(finalRequest.Status is RequestStatus.Approved or RequestStatus.Rejected);

        var decisionNotifications = await db.NotificationRecords
            .Where(n => n.PortalRequestId == req.Id &&
                (n.Template == NotificationTemplate.RequesterApproved || n.Template == NotificationTemplate.RequesterRejected))
            .ToListAsync();
        var expectedTemplate = finalRequest.Status == RequestStatus.Approved
            ? NotificationTemplate.RequesterApproved : NotificationTemplate.RequesterRejected;
        var winningNotification = Assert.Single(decisionNotifications);
        Assert.Equal(expectedTemplate, winningNotification.Template);
        // This end-to-end HTTP test runs on the EF Core InMemory provider, which does not roll back a whole
        // SaveChanges atomically on a concurrency conflict (a documented InMemory-only limitation), so it does
        // not itself prove audit-row rollback. RelationalAtomicityTests proves that same atomicity against a
        // real relational provider (SQLite), where — like SQL Server — SaveChanges is a genuine transaction.

        static string TaskOutcome(Task<PortalRequest> t)
        {
            if (t.IsCompletedSuccessfully) return "ok";
            if (t.Exception?.GetBaseException() is SmartServe.Api.Services.ConcurrentTransitionException) return "conflict";
            throw t.Exception!.GetBaseException();
        }
    }

    [Fact]
    public async Task Concurrent_modification_of_notification_record_during_send_is_logged_not_thrown()
    {
        _factory.Directory.AddUser(new("svc-conflict", "Service Conflict", "svc.conflict@contoso.example"));

        _factory.EmailSender.OnSend = async message =>
        {
            if (!message.Subject.Contains("submitted")) return;
            // Simulate another process touching the same (still-Pending) NotificationRecord mid-send,
            // bumping its RowVersion so this send's own finalize save loses the race.
            await using var racingDb = await DbFactory().CreateDbContextAsync();
            var pending = await racingDb.NotificationRecords
                .Where(n => n.RecipientRole == "Requester" && n.Status == NotificationStatus.Pending)
                .OrderByDescending(n => n.CreatedAt).FirstAsync();
            pending.Reason = "TouchedByConcurrentWriter";
            pending.Status = NotificationStatus.Failed;
            pending.CompletedAt = DateTimeOffset.UtcNow;
            pending.RowVersion = Guid.NewGuid();
            await racingDb.SaveChangesAsync();
        };

        // Submission must still succeed even though the finalize save below will hit a concurrency conflict.
        var req = await CreateAsync(RequestKind.Service, _serviceTypeId, "svc-conflict");

        await using var db = await DbFactory().CreateDbContextAsync();
        var notification = await db.NotificationRecords
            .Where(n => n.PortalRequestId == req.Id && n.RecipientRole == "Requester")
            .OrderByDescending(n => n.CreatedAt).FirstAsync();

        // The concurrent writer's save committed first; this send's own finalize lost the race and was
        // swallowed (logged) rather than thrown or corrupting the already-persisted outcome.
        Assert.Equal("TouchedByConcurrentWriter", notification.Reason);
        Assert.Equal(NotificationStatus.Failed, notification.Status);
    }

    [Fact]
    public async Task Cancellation_during_dispatch_is_recorded_as_failed_not_left_pending()
    {
        _factory.Directory.AddUser(new("svc-cancel", "Service Cancel", "svc.cancel@contoso.example"));
        _factory.EmailSender.OnSend = _ => throw new OperationCanceledException("Simulated cancellation during dispatch");

        var req = await CreateAsync(RequestKind.Service, _serviceTypeId, "svc-cancel");

        await using var db = await DbFactory().CreateDbContextAsync();
        var notification = await db.NotificationRecords
            .Where(n => n.PortalRequestId == req.Id && n.RecipientRole == "Requester")
            .OrderByDescending(n => n.CreatedAt).FirstAsync();

        Assert.Equal(NotificationStatus.Failed, notification.Status);
        Assert.NotNull(notification.CompletedAt);
        Assert.False(string.IsNullOrWhiteSpace(notification.Reason));
    }

    [Fact]
    public async Task Reconciliation_backs_off_a_stale_record_already_finalized_by_a_concurrent_active_send()
    {
        await using var db = await DbFactory().CreateDbContextAsync();
        var requestId = Guid.NewGuid();
        db.PortalRequests.Add(new PortalRequest
        {
            Id = requestId, Kind = RequestKind.Access, RequestTypeId = _accessTypeId,
            Title = "x", Description = "y", RequesterId = "someone", Status = RequestStatus.Submitted
        });
        var staleId = Guid.NewGuid();
        db.NotificationRecords.Add(new NotificationRecord
        {
            Id = staleId, PortalRequestId = requestId, RecipientRole = "Requester",
            Template = NotificationTemplate.RequesterSubmitted, Status = NotificationStatus.Pending,
            LeaseExpiresAt = DateTimeOffset.UtcNow.AddMinutes(-1)
        });
        await db.SaveChangesAsync();

        var reconciler = _factory.Services.GetRequiredService<SmartServe.Api.Services.NotificationReconciliationService>();
        reconciler.OnBeforeSave = async _ =>
        {
            // A real send finalizes this exact record first, bumping its RowVersion.
            await using var racingDb = await DbFactory().CreateDbContextAsync();
            var racing = await racingDb.NotificationRecords.FirstAsync(n => n.Id == staleId);
            racing.Status = NotificationStatus.Accepted;
            racing.Reason = "Accepted (fake sender)";
            racing.CompletedAt = DateTimeOffset.UtcNow;
            racing.RowVersion = Guid.NewGuid();
            await racingDb.SaveChangesAsync();
        };

        var reconciled = await reconciler.ReconcileAsync();
        reconciler.OnBeforeSave = null;

        Assert.Equal(0, reconciled); // the conflicting write already finalized it; reconciliation backs off

        await using var verifyDb = await DbFactory().CreateDbContextAsync();
        var final = await verifyDb.NotificationRecords.FirstAsync(n => n.Id == staleId);
        Assert.Equal(NotificationStatus.Accepted, final.Status); // active send's real outcome wins, not overwritten
    }
}

