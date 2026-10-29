using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;
using SmartServe.Api.Dtos;
using SmartServe.Api.Services;

namespace SmartServe.Api.Controllers;

[ApiController]
[Route("api/requests")]
[Authorize] // all endpoints require an authenticated principal
public class AccessRequestsController : ControllerBase
{
    private readonly SmartServeDbContext _db;
    private readonly WorkflowService _workflow;
    private readonly ILogger<AccessRequestsController> _log;

    public AccessRequestsController(SmartServeDbContext db, WorkflowService workflow,
        ILogger<AccessRequestsController> log)
    {
        _db = db;
        _workflow = workflow;
        _log = log;
    }

    private string UserId =>
        User.FindFirstValue("oid")
        ?? User.FindFirstValue(ClaimTypes.NameIdentifier)
        ?? User.Identity?.Name
        ?? "unknown";

    private string CorrelationId =>
        HttpContext.Request.Headers["x-correlation-id"].FirstOrDefault()
        ?? HttpContext.TraceIdentifier;

    private async Task AuditAsync(Guid? requestId, string action, string? details)
    {
        _db.AuditEntries.Add(new AuditEntry
        {
            AccessRequestId = requestId,
            ActorId = UserId,
            Action = action,
            Details = details,
            CorrelationId = CorrelationId
        });
        await _db.SaveChangesAsync();
    }

    private static RequestResponse ToResponse(AccessRequest r) => new(
        r.Id, r.Title, r.Description, r.Category, r.Status, r.RequesterId,
        r.AssignedToId, r.RequiresSecurityReview, r.CreatedAt, r.UpdatedAt);

    // FR: Employee creates a request. (US-001)
    [HttpPost]
    [Authorize(Policy = "CanCreateRequest")]
    public async Task<ActionResult<RequestResponse>> Create(CreateRequestDto dto)
    {
        var req = new AccessRequest
        {
            Title = dto.Title,
            Description = dto.Description,
            Category = dto.Category,
            RequesterId = UserId,
            RequiresSecurityReview = _workflow.RequiresSecurityReview(dto.Category),
            Status = RequestStatus.Submitted
        };
        _db.AccessRequests.Add(req);
        await _db.SaveChangesAsync();
        await AuditAsync(req.Id, "RequestCreated", $"category={dto.Category}");
        _log.LogInformation("Request {Id} created by {User}", req.Id, UserId);
        return CreatedAtAction(nameof(GetById), new { id = req.Id }, ToResponse(req));
    }

    // Employees see only their own requests; approvers/admins/auditors see all.
    [HttpGet]
    public async Task<ActionResult<IEnumerable<RequestResponse>>> List()
    {
        IQueryable<AccessRequest> q = _db.AccessRequests.AsNoTracking();
        if (User.IsInRole(Roles.Employee) &&
            !(User.IsInRole(Roles.Manager) || User.IsInRole(Roles.ItAdmin) ||
              User.IsInRole(Roles.AppAdmin) || User.IsInRole(Roles.Auditor) ||
              User.IsInRole(Roles.SecurityReviewer)))
        {
            q = q.Where(r => r.RequesterId == UserId);
        }
        var items = await q.OrderByDescending(r => r.CreatedAt).ToListAsync();
        return Ok(items.Select(ToResponse));
    }

    [HttpGet("{id:guid}")]
    public async Task<ActionResult<RequestResponse>> GetById(Guid id)
    {
        var req = await _db.AccessRequests.AsNoTracking().FirstOrDefaultAsync(r => r.Id == id);
        if (req is null) return NotFound();

        // Enforce ownership for plain employees (server-side authorization).
        if (req.RequesterId != UserId && OnlyEmployee())
            return Forbid();

        return Ok(ToResponse(req));
    }

    // Manager/Security/IT decision on the current stage. (US-003)
    [HttpPost("{id:guid}/decision")]
    [Authorize(Policy = "CanApprove")]
    public async Task<ActionResult<RequestResponse>> Decide(Guid id, DecisionDto dto)
    {
        var req = await _db.AccessRequests.Include(r => r.Approvals)
            .FirstOrDefaultAsync(r => r.Id == id);
        if (req is null) return NotFound();

        // An employee may never approve their own request, even if mis-assigned a role.
        if (req.RequesterId == UserId) return Forbid();

        var stage = _workflow.CurrentStage(req);
        if (stage is null) return BadRequest("Request is not awaiting a decision.");

        // Stage-specific role enforcement.
        if (stage == "Manager" && !User.IsInRole(Roles.Manager)) return Forbid();
        if (stage == "Security" && !User.IsInRole(Roles.SecurityReviewer)) return Forbid();
        if (stage == "IT" && !User.IsInRole(Roles.ItAdmin)) return Forbid();

        req.Approvals.Add(new ApprovalStep
        {
            Stage = stage,
            DecidedById = UserId,
            Approved = dto.Approved,
            Notes = dto.Notes,
            DecidedAt = DateTimeOffset.UtcNow
        });
        req.Status = _workflow.Advance(req, stage, dto.Approved);
        req.UpdatedAt = DateTimeOffset.UtcNow;
        await _db.SaveChangesAsync();
        await AuditAsync(req.Id, "Decision", $"stage={stage};approved={dto.Approved}");
        return Ok(ToResponse(req));
    }

    // Employee confirms provisioning; closes the request. (US-004)
    [HttpPost("{id:guid}/confirm")]
    public async Task<ActionResult<RequestResponse>> Confirm(Guid id)
    {
        var req = await _db.AccessRequests.FirstOrDefaultAsync(r => r.Id == id);
        if (req is null) return NotFound();
        if (req.RequesterId != UserId) return Forbid();
        if (req.Status is not (RequestStatus.Provisioned or RequestStatus.AwaitingConfirmation))
            return BadRequest("Request is not awaiting confirmation.");

        req.Status = RequestStatus.Closed;
        req.ClosedAt = DateTimeOffset.UtcNow;
        req.UpdatedAt = DateTimeOffset.UtcNow;
        await _db.SaveChangesAsync();
        await AuditAsync(req.Id, "Closed", null);
        return Ok(ToResponse(req));
    }

    [HttpPost("{id:guid}/comments")]
    public async Task<IActionResult> AddComment(Guid id, CommentDto dto)
    {
        var req = await _db.AccessRequests.FirstOrDefaultAsync(r => r.Id == id);
        if (req is null) return NotFound();
        if (req.RequesterId != UserId && OnlyEmployee()) return Forbid();

        _db.Comments.Add(new RequestComment
        {
            AccessRequestId = id, AuthorId = UserId, Body = dto.Body
        });
        await _db.SaveChangesAsync();
        await AuditAsync(id, "CommentAdded", null);
        return NoContent();
    }

    private bool OnlyEmployee() =>
        User.IsInRole(Roles.Employee) &&
        !(User.IsInRole(Roles.Manager) || User.IsInRole(Roles.ItAdmin) ||
          User.IsInRole(Roles.AppAdmin) || User.IsInRole(Roles.Auditor) ||
          User.IsInRole(Roles.SecurityReviewer));
}
