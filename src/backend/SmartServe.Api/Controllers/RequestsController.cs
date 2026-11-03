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
[Authorize]
public class RequestsController : ControllerBase
{
    private readonly IDbContextFactory<SmartServeDbContext> _dbFactory;
    private readonly WorkflowService _workflow;

    public RequestsController(IDbContextFactory<SmartServeDbContext> dbFactory, WorkflowService workflow)
    {
        _dbFactory = dbFactory;
        _workflow = workflow;
    }

    private string UserId =>
        User.FindFirstValue("oid")
        ?? User.FindFirstValue(ClaimTypes.NameIdentifier)
        ?? throw new InvalidOperationException("Authenticated principal has no user id claim.");

    internal static RequestResponse ToResponse(PortalRequest r) => new(
        r.Id, r.Kind, r.RequestTypeId, r.RequestType?.Name ?? string.Empty, r.Title, r.Description,
        r.Status, r.RequesterId, r.ManagerId, r.CreatedAt, r.UpdatedAt);

    [HttpPost]
    [Authorize(Policy = "CanCreateRequest")] // Employee submission confirmed; Manager/ItAdmin/AppAdmin submission is (proposed)
    public async Task<ActionResult<RequestResponse>> Create(CreateRequestDto dto, CancellationToken ct)
    {
        try
        {
            var request = await _workflow.SubmitAsync(dto.Kind, dto.RequestTypeId, dto.Title, dto.Description, UserId, ct);
            var response = await LoadResponseAsync(request.Id, ct);
            return CreatedAtAction(nameof(GetById), new { id = request.Id }, response);
        }
        catch (InvalidOperationException ex)
        {
            return BadRequest(ex.Message);
        }
    }

    // Confirmed: Employee policy, always filtered to the caller's own requests — no other role may use this endpoint.
    [HttpGet]
    [Authorize(Policy = "CanViewOwnRequests")]
    public async Task<ActionResult<IEnumerable<RequestResponse>>> List(CancellationToken ct)
    {
        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var items = await db.PortalRequests.Include(r => r.RequestType).AsNoTracking()
            .Where(r => r.RequesterId == UserId)
            .OrderByDescending(r => r.CreatedAt)
            .ToListAsync(ct);
        return Ok(items.Select(ToResponse));
    }

    // Confirmed: Employee policy, always filtered to ownership — managers/IT admins/app admins use their own (proposed) workflow endpoints instead.
    [HttpGet("{id:guid}")]
    [Authorize(Policy = "CanViewOwnRequests")]
    public async Task<ActionResult<RequestResponse>> GetById(Guid id, CancellationToken ct)
    {
        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var req = await db.PortalRequests.Include(r => r.RequestType).AsNoTracking()
            .FirstOrDefaultAsync(r => r.Id == id && r.RequesterId == UserId, ct);
        if (req is null) return NotFound();

        return Ok(ToResponse(req));
    }

    // (proposed) endpoint shape and manager permission mapping; manager-decision workflow behavior itself is confirmed.
    [HttpPost("{id:guid}/decision")]
    [Authorize(Policy = "CanApprove")]
    public async Task<ActionResult<RequestResponse>> Decide(Guid id, DecisionDto dto, CancellationToken ct)
    {
        try
        {
            await _workflow.DecideAsync(id, UserId, dto.Approved, dto.Notes, ct);
            return Ok(await LoadResponseAsync(id, ct));
        }
        catch (KeyNotFoundException)
        {
            return NotFound();
        }
        catch (InvalidOperationException ex)
        {
            return BadRequest(ex.Message);
        }
    }

    // (proposed) endpoint shape and IT-admin permission mapping; fulfilment workflow behavior itself is confirmed.
    [HttpPost("{id:guid}/fulfil")]
    [Authorize(Policy = "CanFulfil")]
    public async Task<ActionResult<RequestResponse>> Fulfil(Guid id, CancellationToken ct)
    {
        try
        {
            await _workflow.FulfilAsync(id, UserId, ct);
            return Ok(await LoadResponseAsync(id, ct));
        }
        catch (KeyNotFoundException)
        {
            return NotFound();
        }
        catch (InvalidOperationException ex)
        {
            return BadRequest(ex.Message);
        }
    }

    // (proposed) IT-admin action performing the deferred Submitted -> UnderReview transition, not merely a resend.
    [HttpPost("{id:guid}/retry-routing")]
    [Authorize(Policy = "CanRetryRouting")]
    public async Task<ActionResult<RequestResponse>> RetryRouting(Guid id, CancellationToken ct)
    {
        try
        {
            await _workflow.TryRouteToManagerAsync(id, UserId, ct);
            return Ok(await LoadResponseAsync(id, ct));
        }
        catch (KeyNotFoundException)
        {
            return NotFound();
        }
    }

    private async Task<RequestResponse> LoadResponseAsync(Guid id, CancellationToken ct)
    {
        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var req = await db.PortalRequests.Include(r => r.RequestType).AsNoTracking().FirstAsync(r => r.Id == id, ct);
        return ToResponse(req);
    }
}
