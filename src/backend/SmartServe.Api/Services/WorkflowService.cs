using Microsoft.EntityFrameworkCore;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;
using SmartServe.Api.Services.Directory;

namespace SmartServe.Api.Services;

public record RoutingResult(bool Advanced, PortalRequest Request, string? Reason);

/// <summary>Thrown when a transition's concurrency token no longer matches, i.e. a competing call already transitioned the request.</summary>
public class ConcurrentTransitionException : InvalidOperationException
{
    public ConcurrentTransitionException(string message) : base(message) { }
}

/// <summary>Orchestrates request submission/transitions: every status change's audit row is in the same SaveChanges as the status update, before any related email.</summary>
public class WorkflowService
{
    private readonly IDbContextFactory<SmartServeDbContext> _dbFactory;
    private readonly IDirectoryService _directory;
    private readonly NotificationService _notifications;

    public WorkflowService(IDbContextFactory<SmartServeDbContext> dbFactory, IDirectoryService directory,
        NotificationService notifications)
    {
        _dbFactory = dbFactory;
        _directory = directory;
        _notifications = notifications;
    }

    /// <summary>Test seam only: invoked right before a transition's SaveChangesAsync, to let tests force a genuine concurrency race.</summary>
    public Func<Guid, Task>? OnBeforeTransitionSave { get; set; }

    public async Task<PortalRequest> SubmitAsync(RequestKind kind, Guid requestTypeId, string title, string description,
        string actorId, CancellationToken ct = default)
    {
        Guid requestId;
        await using (var db = await _dbFactory.CreateDbContextAsync(ct))
        {
            var requestType = await db.RequestTypes
                .FirstOrDefaultAsync(t => t.Id == requestTypeId && t.Kind == kind && t.IsActive, ct)
                ?? throw new InvalidOperationException("Unknown or inactive request type for this kind.");

            var request = new PortalRequest
            {
                Kind = kind,
                RequestTypeId = requestTypeId,
                Title = title,
                Description = description,
                RequesterId = actorId,
                Status = RequestStatus.Submitted
            };
            db.PortalRequests.Add(request);
            // Same SaveChanges as the create: one audit record, old status null -> Submitted.
            db.RequestAudits.Add(new RequestAudit
            {
                PortalRequestId = request.Id,
                ActorId = actorId,
                OldStatus = null,
                NewStatus = RequestStatus.Submitted
            });
            await db.SaveChangesAsync(ct);
            requestId = request.Id;
        }

        await _notifications.SendAsync(requestId, "Requester", NotificationTemplate.RequesterSubmitted, actorId, ct);

        if (kind == RequestKind.Access)
        {
            // (proposed) trigger: routing immediately on submission is an implementation choice, not confirmed timing.
            await TryRouteToManagerAsync(requestId, actorId, ct);
        }
        // (proposed/open question): no further service-request transitions are confirmed yet.

        return await GetAsync(requestId, ct);
    }

/// <summary>Attempts the Submitted -> UnderReview transition once the requester's manager is resolvable; used by submission and the (proposed) IT-admin retry action.</summary>
    public async Task<RoutingResult> TryRouteToManagerAsync(Guid requestId, string actorId, CancellationToken ct = default)
    {
        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var request = await db.PortalRequests.FirstOrDefaultAsync(r => r.Id == requestId, ct)
            ?? throw new KeyNotFoundException($"Request {requestId} not found.");

        if (request.Kind != RequestKind.Access || request.Status != RequestStatus.Submitted)
            return new RoutingResult(false, request, "NotEligible");

        DirectoryUser? manager;
        try
        {
            manager = await _directory.GetManagerAsync(request.RequesterId, ct);
        }
        catch (DirectoryUnavailableException ex)
        {
            await _notifications.RecordFailedAsync(requestId, "Manager", NotificationTemplate.ManagerWaitingApproval,
                $"DirectoryUnavailable:{ex.Message}", ct);
            return new RoutingResult(false, request, "DirectoryUnavailable");
        }

        if (manager is null)
        {
            // Confirmed rule: request stays Submitted; a NotSent manager notification records the reason.
            await _notifications.RecordNotSentAsync(requestId, "Manager", NotificationTemplate.ManagerWaitingApproval,
                "ManagerUnresolved", ct);
            return new RoutingResult(false, request, "ManagerUnresolved");
        }

        request.ManagerId = manager.Id;
        request.Status = RequestStatus.UnderReview;
        request.UpdatedAt = DateTimeOffset.UtcNow;
        request.RowVersion = Guid.NewGuid();
        db.RequestAudits.Add(new RequestAudit
        {
            PortalRequestId = requestId,
            ActorId = actorId,
            OldStatus = RequestStatus.Submitted,
            NewStatus = RequestStatus.UnderReview
        });
        try
        {
            if (OnBeforeTransitionSave is not null) await OnBeforeTransitionSave(requestId);
            // Status + audit are committed here, BEFORE the manager email is dispatched below.
            await db.SaveChangesAsync(ct);
        }
        catch (DbUpdateConcurrencyException)
        {
            // A competing call already moved this request off Submitted; this call does not advance or notify again.
            return new RoutingResult(false, request, "ConcurrentModification");
        }

        await _notifications.SendAsync(requestId, "Manager", NotificationTemplate.ManagerWaitingApproval, actorId, ct);
        await _notifications.SendAsync(requestId, "Requester", NotificationTemplate.RequesterUnderReview, actorId, ct);

        return new RoutingResult(true, request, null);
    }

    public async Task<PortalRequest> DecideAsync(Guid requestId, string actorId, bool approved, string? notes,
        CancellationToken ct = default)
    {
        await using (var db = await _dbFactory.CreateDbContextAsync(ct))
        {
            var request = await db.PortalRequests.FirstOrDefaultAsync(r => r.Id == requestId, ct)
                ?? throw new KeyNotFoundException($"Request {requestId} not found.");

            if (request.Kind != RequestKind.Access)
                throw new InvalidOperationException("Only access requests support manager decisions.");
            if (request.Status != RequestStatus.UnderReview)
                throw new InvalidOperationException("Request is not awaiting a decision.");

            var oldStatus = request.Status;
            request.Status = approved ? RequestStatus.Approved : RequestStatus.Rejected;
            request.UpdatedAt = DateTimeOffset.UtcNow;
            request.RowVersion = Guid.NewGuid();
            db.RequestAudits.Add(new RequestAudit
            {
                PortalRequestId = requestId,
                ActorId = actorId,
                OldStatus = oldStatus,
                NewStatus = request.Status
            });
            try
            {
                if (OnBeforeTransitionSave is not null) await OnBeforeTransitionSave(requestId);
                await db.SaveChangesAsync(ct);
            }
            catch (DbUpdateConcurrencyException)
            {
                // A competing decision already changed this request's status out from under this one.
                throw new ConcurrentTransitionException($"Request {requestId} was concurrently modified; retry the decision.");
            }
        }

        await _notifications.SendAsync(requestId, "Requester",
            approved ? NotificationTemplate.RequesterApproved : NotificationTemplate.RequesterRejected, actorId, ct);

        return await GetAsync(requestId, ct);
    }

    public async Task<PortalRequest> FulfilAsync(Guid requestId, string actorId, CancellationToken ct = default)
    {
        await using (var db = await _dbFactory.CreateDbContextAsync(ct))
        {
            var request = await db.PortalRequests.FirstOrDefaultAsync(r => r.Id == requestId, ct)
                ?? throw new KeyNotFoundException($"Request {requestId} not found.");

            if (request.Status != RequestStatus.Approved)
                throw new InvalidOperationException("Only an Approved request can be fulfilled.");

            request.Status = RequestStatus.Fulfilled;
            request.FulfilledById = actorId;
            request.UpdatedAt = DateTimeOffset.UtcNow;
            request.RowVersion = Guid.NewGuid();
            db.RequestAudits.Add(new RequestAudit
            {
                PortalRequestId = requestId,
                ActorId = actorId,
                OldStatus = RequestStatus.Approved,
                NewStatus = RequestStatus.Fulfilled
            });
            try
            {
                if (OnBeforeTransitionSave is not null) await OnBeforeTransitionSave(requestId);
                await db.SaveChangesAsync(ct);
            }
            catch (DbUpdateConcurrencyException)
            {
                // A competing fulfilment call already transitioned this request.
                throw new ConcurrentTransitionException($"Request {requestId} was concurrently modified; retry fulfilment.");
            }
        }

        await _notifications.SendAsync(requestId, "Requester", NotificationTemplate.RequesterFulfilled, actorId, ct);

        return await GetAsync(requestId, ct);
    }

    public async Task<PortalRequest> GetAsync(Guid requestId, CancellationToken ct = default)
    {
        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        return await db.PortalRequests.AsNoTracking().FirstAsync(r => r.Id == requestId, ct);
    }
}
