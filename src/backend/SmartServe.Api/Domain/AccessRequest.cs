using System.ComponentModel.DataAnnotations;

namespace SmartServe.Api.Domain;

/// <summary>A service/access request raised by an employee. Traces to PRD-FR-001.</summary>
public class AccessRequest
{
    public Guid Id { get; set; } = Guid.NewGuid();

    [Required, MaxLength(200)]
    public string Title { get; set; } = string.Empty;

    [Required, MaxLength(4000)]
    public string Description { get; set; } = string.Empty;

    public RequestCategory Category { get; set; }

    public RequestStatus Status { get; set; } = RequestStatus.Submitted;

    /// <summary>Entra ID object id / UPN of the requester.</summary>
    [Required, MaxLength(200)]
    public string RequesterId { get; set; } = string.Empty;

    [MaxLength(200)]
    public string? AssignedToId { get; set; }

    /// <summary>Set true for sensitive categories that require security review.</summary>
    public bool RequiresSecurityReview { get; set; }

    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
    public DateTimeOffset? UpdatedAt { get; set; }
    public DateTimeOffset? ClosedAt { get; set; }

    public List<RequestComment> Comments { get; set; } = new();
    public List<ApprovalStep> Approvals { get; set; } = new();
}

public class RequestComment
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid AccessRequestId { get; set; }

    [Required, MaxLength(200)]
    public string AuthorId { get; set; } = string.Empty;

    [Required, MaxLength(4000)]
    public string Body { get; set; } = string.Empty;

    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}

public class ApprovalStep
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid AccessRequestId { get; set; }

    [Required, MaxLength(50)]
    public string Stage { get; set; } = string.Empty;   // Manager | Security | IT

    [MaxLength(200)]
    public string? DecidedById { get; set; }

    public bool? Approved { get; set; }

    [MaxLength(2000)]
    public string? Notes { get; set; }

    public DateTimeOffset? DecidedAt { get; set; }
}

/// <summary>Immutable audit trail entry. Append-only; consumed by the Auditor role.</summary>
public class AuditEntry
{
    public long Id { get; set; }
    public Guid? AccessRequestId { get; set; }

    [Required, MaxLength(200)]
    public string ActorId { get; set; } = string.Empty;

    [Required, MaxLength(100)]
    public string Action { get; set; } = string.Empty;

    [MaxLength(2000)]
    public string? Details { get; set; }

    public DateTimeOffset Timestamp { get; set; } = DateTimeOffset.UtcNow;

    /// <summary>Correlation id linking frontend/backend operations.</summary>
    [MaxLength(100)]
    public string? CorrelationId { get; set; }
}
