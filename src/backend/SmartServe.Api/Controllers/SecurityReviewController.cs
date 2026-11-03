using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;
using SmartServe.Api.Dtos;

namespace SmartServe.Api.Controllers;

/// <summary>SecurityReviewer read-only visibility of ACCESS requests only — no service requests, no decisions.</summary>
[ApiController]
[Route("api/security")]
[Authorize(Policy = "CanSecurityReview")]
public class SecurityReviewController : ControllerBase
{
    private const int DefaultPageSize = 50; // (proposed)
    private const int MaxPageSize = 200;

    private readonly IDbContextFactory<SmartServeDbContext> _dbFactory;

    public SecurityReviewController(IDbContextFactory<SmartServeDbContext> dbFactory) => _dbFactory = dbFactory;

    [HttpGet("access-requests")]
    public async Task<ActionResult<PagedResult<RequestResponse>>> ListAccessRequests(
        [FromQuery] int page = 1, [FromQuery] int pageSize = DefaultPageSize, CancellationToken ct = default)
    {
        page = Math.Max(page, 1);
        pageSize = Math.Clamp(pageSize, 1, MaxPageSize);

        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var query = db.PortalRequests.Include(r => r.RequestType).AsNoTracking()
            .Where(r => r.Kind == RequestKind.Access)
            .OrderByDescending(r => r.CreatedAt);
        var total = await query.CountAsync(ct);
        var items = await query.Skip((page - 1) * pageSize).Take(pageSize).ToListAsync(ct);
        return Ok(new PagedResult<RequestResponse>(items.Select(RequestsController.ToResponse).ToList(), page, pageSize, total));
    }
}
