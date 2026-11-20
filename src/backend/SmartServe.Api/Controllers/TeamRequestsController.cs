using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SmartServe.Api.Data;
using SmartServe.Api.Dtos;
using SmartServe.Api.Services.Teams;

namespace SmartServe.Api.Controllers;

/// <summary>Manager-only visibility of requests within the caller's currently-authorized team scope (ARCH-COMP-004, TASK-010). Scope is resolved fresh on every call via <see cref="ITeamScopeProvider"/> — never from any stored/cached field on the request — so a manager reassignment takes effect immediately and an outage denies access rather than falling back to stale data. (proposed route shape)</summary>
[ApiController]
[Route("api/team")]
[Authorize(Policy = "CanViewTeamRequests")]
public class TeamRequestsController : ControllerBase
{
    private const int DefaultPageSize = 50; // (proposed)
    private const int MaxPageSize = 200;

    private readonly IDbContextFactory<SmartServeDbContext> _dbFactory;
    private readonly ITeamScopeProvider _teamScope;

    public TeamRequestsController(IDbContextFactory<SmartServeDbContext> dbFactory, ITeamScopeProvider teamScope)
    {
        _dbFactory = dbFactory;
        _teamScope = teamScope;
    }

    private string UserId =>
        User.FindFirstValue("oid")
        ?? User.FindFirstValue(ClaimTypes.NameIdentifier)
        ?? throw new InvalidOperationException("Authenticated principal has no user id claim.");

    // Confirmed: Manager policy. Scope is resolved at request time via the swappable team-scope provider;
    // if the authoritative source cannot verify scope, deny (fail-closed) rather than disclose any data.
    [HttpGet("requests")]
    public async Task<ActionResult<PagedResult<RequestResponse>>> ListTeamRequests(
        [FromQuery] int page = 1, [FromQuery] int pageSize = DefaultPageSize, CancellationToken ct = default)
    {
        page = Math.Max(page, 1);
        pageSize = Math.Clamp(pageSize, 1, MaxPageSize);

        var scope = await _teamScope.ResolveTeamScopeAsync(UserId, ct);
        if (!scope.IsResolved)
            return Forbid();

        var memberIds = scope.MemberIds!;
        if (memberIds.Count == 0)
            return Ok(new PagedResult<RequestResponse>(new List<RequestResponse>(), page, pageSize, 0));

        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var query = db.PortalRequests.Include(r => r.RequestType).AsNoTracking()
            .Where(r => memberIds.Contains(r.RequesterId))
            .OrderByDescending(r => r.CreatedAt);
        var total = await query.CountAsync(ct);
        var items = await query.Skip((page - 1) * pageSize).Take(pageSize).ToListAsync(ct);
        return Ok(new PagedResult<RequestResponse>(items.Select(RequestsController.ToResponse).ToList(), page, pageSize, total));
    }
}
