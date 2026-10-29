using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;

namespace SmartServe.Api.Controllers;

/// <summary>Read-only audit trail. Restricted to the Auditor role.</summary>
[ApiController]
[Route("api/audit")]
[Authorize(Policy = "CanAudit")]
public class AuditController : ControllerBase
{
    private readonly SmartServeDbContext _db;

    public AuditController(SmartServeDbContext db) => _db = db;

    [HttpGet]
    public async Task<ActionResult<IEnumerable<AuditEntry>>> List([FromQuery] Guid? requestId)
    {
        IQueryable<AuditEntry> q = _db.AuditEntries.AsNoTracking();
        if (requestId is not null) q = q.Where(a => a.AccessRequestId == requestId);
        return Ok(await q.OrderByDescending(a => a.Timestamp).Take(500).ToListAsync());
    }
}
