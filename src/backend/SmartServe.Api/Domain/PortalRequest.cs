using System.ComponentModel.DataAnnotations;

namespace SmartServe.Api.Domain;

/// <summary>Consolidated access/service request entity (proposed name: PortalRequest, replacing AccessRequest).</summary>
public class PortalRequest
{
    public Guid Id { get; set; } = Guid.NewGuid();

    public RequestKind Kind { get; set; }

    public Guid RequestTypeId { get; set; }
    public RequestType? RequestType { get; set; }

    [Required, MaxLength(200)]
    public string Title { get; set; } = string.Empty;

    [Required, MaxLength(4000)]
    public string Description { get; set; } = string.Empty;

    public RequestStatus Status { get; set; } = RequestStatus.Submitted;

    /// <summary>Entra ID object id of the requester.</summary>
    [Required, MaxLength(200)]
    public string RequesterId { get; set; } = string.Empty;

    /// <summary>Snapshot of the requester's manager at submission time, used only for notification routing (access requests only). Not authoritative for team-view authorization: that is resolved fresh at request time via <c>ITeamScopeProvider</c> so a later manager reassignment is reflected immediately.</summary>
    [MaxLength(200)]
    public string? ManagerId { get; set; }

    [MaxLength(200)]
    public string? FulfilledById { get; set; }

    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
    public DateTimeOffset? UpdatedAt { get; set; }

    /// <summary>Concurrency token: guards against duplicate/conflicting transitions from simultaneous calls. App-managed GUID (not DB-generated rowversion) so the guard works identically on SQL Server and the InMemory test provider.</summary>
    public Guid RowVersion { get; set; } = Guid.NewGuid();
}

/// <summary>Request type catalog managed by app admins (create/edit/deactivate; no reactivation).</summary>
public class RequestType
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public RequestKind Kind { get; set; }

    [Required, MaxLength(200)]
    public string Name { get; set; } = string.Empty;

    [MaxLength(2000)]
    public string? Description { get; set; }

    public bool IsActive { get; set; } = true;

    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
    public DateTimeOffset? UpdatedAt { get; set; }
    public DateTimeOffset? DeactivatedAt { get; set; }
}

/// <summary>Shared audit mechanism for status changes on both access and service requests (one append-only table).</summary>
public class RequestAudit
{
    public long Id { get; set; }
    public Guid PortalRequestId { get; set; }

    [Required, MaxLength(200)]
    public string ActorId { get; set; } = string.Empty;

    /// <summary>Null only for the very first Submitted record.</summary>
    public RequestStatus? OldStatus { get; set; }

    public RequestStatus NewStatus { get; set; }

    public DateTimeOffset Timestamp { get; set; } = DateTimeOffset.UtcNow;
}

/// <summary>Authoritative, persisted notification record (EF Core table); must end Accepted, NotSent or Failed.</summary>
public class NotificationRecord
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid PortalRequestId { get; set; }

    public NotificationTemplate Template { get; set; }

    /// <summary>"Requester" or "Manager".</summary>
    [Required, MaxLength(50)]
    public string RecipientRole { get; set; } = string.Empty;

    [MaxLength(320)]
    public string? RecipientAddress { get; set; }

    public NotificationStatus Status { get; set; } = NotificationStatus.Pending;

    [MaxLength(200)]
    public string? Reason { get; set; }

    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;

    /// <summary>Lease window; reconciliation only touches records whose lease has expired.</summary>
    public DateTimeOffset LeaseExpiresAt { get; set; }

    public DateTimeOffset? CompletedAt { get; set; }

    /// <summary>Concurrency token: lets reconciliation detect and skip a record an active send already finalized. App-managed GUID (not DB-generated rowversion) so the guard works identically on SQL Server and the InMemory test provider.</summary>
    public Guid RowVersion { get; set; } = Guid.NewGuid();
}

/// <summary>Minimal, content-free record of a retention disposal action, for auditability of the disposal itself. Preserves the review-timing facts (<see cref="SubmittedAt"/>, <see cref="FirstReviewAt"/>) that were already recorded on the disposed request's audit trail, so NFR-003 reporting (<c>ReviewMetricsService</c>) is unaffected by later disposal — a disposed request keeps counting in the historical metric exactly as it did before disposal. (proposed, TASK-014)</summary>
public class RetentionDisposalRecord
{
    public long Id { get; set; }
    public Guid PortalRequestId { get; set; }
    public RequestKind Kind { get; set; }
    public RequestStatus FinalStatus { get; set; }
    public DateTimeOffset SubmittedAt { get; set; }

    /// <summary>Timestamp of the first post-submission status change (the "initial review", per the provisional NFR-003 definition), captured before the underlying audit rows were deleted. Null if the request was disposed without ever being reviewed.</summary>
    public DateTimeOffset? FirstReviewAt { get; set; }

    public DateTimeOffset DisposedAt { get; set; } = DateTimeOffset.UtcNow;
}
