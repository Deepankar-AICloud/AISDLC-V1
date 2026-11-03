using System.ComponentModel.DataAnnotations;
using SmartServe.Api.Domain;

namespace SmartServe.Api.Dtos;

// (proposed) submission fields: BRD/PRD leave exact form fields and confirmation wording open questions.
public record CreateRequestDto(
    RequestKind Kind,
    Guid RequestTypeId,
    [Required, MaxLength(200)] string Title,
    [Required, MaxLength(4000)] string Description);

public record DecisionDto(
    bool Approved,
    [MaxLength(2000)] string? Notes);

public record RequestResponse(
    Guid Id,
    RequestKind Kind,
    Guid RequestTypeId,
    string RequestTypeName,
    string Title,
    string Description,
    RequestStatus Status,
    string RequesterId,
    string? ManagerId,
    DateTimeOffset CreatedAt,
    DateTimeOffset? UpdatedAt);

public record AuditEntryResponse(
    long Id,
    Guid PortalRequestId,
    string ActorId,
    RequestStatus? OldStatus,
    RequestStatus NewStatus,
    DateTimeOffset Timestamp);

public record CreateRequestTypeDto(
    RequestKind Kind,
    [Required, MaxLength(200)] string Name,
    [MaxLength(2000)] string? Description);

public record UpdateRequestTypeDto(
    [Required, MaxLength(200)] string Name,
    [MaxLength(2000)] string? Description);

public record RequestTypeResponse(
    Guid Id,
    RequestKind Kind,
    string Name,
    string? Description,
    bool IsActive,
    DateTimeOffset CreatedAt,
    DateTimeOffset? UpdatedAt,
    DateTimeOffset? DeactivatedAt);

public record PagedResult<T>(
    IReadOnlyList<T> Items,
    int Page,
    int PageSize,
    int TotalCount);
