using System.ComponentModel.DataAnnotations;
using SmartServe.Api.Domain;

namespace SmartServe.Api.Dtos;

public record CreateRequestDto(
    [Required, MaxLength(200)] string Title,
    [Required, MaxLength(4000)] string Description,
    RequestCategory Category);

public record DecisionDto(
    bool Approved,
    [MaxLength(2000)] string? Notes);

public record CommentDto(
    [Required, MaxLength(4000)] string Body);

public record RequestResponse(
    Guid Id,
    string Title,
    string Description,
    RequestCategory Category,
    RequestStatus Status,
    string RequesterId,
    string? AssignedToId,
    bool RequiresSecurityReview,
    DateTimeOffset CreatedAt,
    DateTimeOffset? UpdatedAt);
