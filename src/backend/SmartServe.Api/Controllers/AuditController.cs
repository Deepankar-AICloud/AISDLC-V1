using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SmartServe.Api.Data;
using SmartServe.Api.Dtos;

namespace SmartServe.Api.Controllers;

/// <summary>Auditor read-only access to ALL requests (access and service) and full audit history is confirmed;
/// also granting AppAdmin the same read-all access is (proposed), not stated in any source artifact.</summary>
[ApiController]
[Route("api/audit")]
[Authorize(Policy = "CanAudit")]
public class AuditController : ControllerBase
{
    private const int DefaultPageSize = 50; // (proposed)
    private const int MaxPageSize = 200;

    private readonly IDbContextFactory<SmartServeDbContext> _dbFactory;

    public AuditController(IDbContextFactory<SmartServeDbContext> dbFactory) => _dbFactory = dbFactory;

    [HttpGet("requests")]
    public async Task<ActionResult<PagedResult<RequestResponse>>> ListAllRequests(
        [FromQuery] int page = 1, [FromQuery] int pageSize = DefaultPageSize, CancellationToken ct = default)
    {
        (page, pageSize) = Normalize(page, pageSize);
        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var query = db.PortalRequests.Include(r => r.RequestType).AsNoTracking().OrderByDescending(r => r.CreatedAt);
        var total = await query.CountAsync(ct);
        var items = await query.Skip((page - 1) * pageSize).Take(pageSize).ToListAsync(ct);
        return Ok(new PagedResult<RequestResponse>(items.Select(RequestsController.ToResponse).ToList(), page, pageSize, total));
    }

    [HttpGet("requests/{id:guid}/history")]
    public async Task<ActionResult<PagedResult<AuditEntryResponse>>> History(Guid id,
        [FromQuery] int page = 1, [FromQuery] int pageSize = DefaultPageSize, CancellationToken ct = default)
    {
        (page, pageSize) = Normalize(page, pageSize);
        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var query = db.RequestAudits.AsNoTracking().Where(a => a.PortalRequestId == id).OrderBy(a => a.Timestamp);
        var total = await query.CountAsync(ct);
        var items = await query.Skip((page - 1) * pageSize).Take(pageSize)
            .Select(a => new AuditEntryResponse(a.Id, a.PortalRequestId, a.ActorId, a.OldStatus, a.NewStatus, a.Timestamp))
            .ToListAsync(ct);
        return Ok(new PagedResult<AuditEntryResponse>(items, page, pageSize, total));
    }

    private static (int Page, int PageSize) Normalize(int page, int pageSize) =>
        (Math.Max(page, 1), Math.Clamp(pageSize, 1, MaxPageSize));
}
