using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;
using SmartServe.Api.Dtos;

namespace SmartServe.Api.Controllers;

/// <summary>App-admin managed catalog of request types: create, edit, deactivate (confirmed; no reactivation).</summary>
[ApiController]
[Route("api/request-types")]
[Authorize]
public class RequestTypesController : ControllerBase
{
    private readonly IDbContextFactory<SmartServeDbContext> _dbFactory;

    public RequestTypesController(IDbContextFactory<SmartServeDbContext> dbFactory) => _dbFactory = dbFactory;

    private static RequestTypeResponse ToResponse(RequestType t) => new(
        t.Id, t.Kind, t.Name, t.Description, t.IsActive, t.CreatedAt, t.UpdatedAt, t.DeactivatedAt);

    // Read access for any authenticated user is (proposed).
    [HttpGet]
    [Authorize(Policy = "CanReadRequestTypes")]
    public async Task<ActionResult<IEnumerable<RequestTypeResponse>>> List(CancellationToken ct)
    {
        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var items = await db.RequestTypes.AsNoTracking().OrderBy(t => t.Kind).ThenBy(t => t.Name).ToListAsync(ct);
        return Ok(items.Select(ToResponse));
    }

    [HttpPost]
    [Authorize(Policy = "CanAdminister")]
    public async Task<ActionResult<RequestTypeResponse>> Create(CreateRequestTypeDto dto, CancellationToken ct)
    {
        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var type = new RequestType { Kind = dto.Kind, Name = dto.Name, Description = dto.Description };
        db.RequestTypes.Add(type);
        await db.SaveChangesAsync(ct);
        return CreatedAtAction(nameof(List), ToResponse(type));
    }

    [HttpPut("{id:guid}")]
    [Authorize(Policy = "CanAdminister")]
    public async Task<ActionResult<RequestTypeResponse>> Update(Guid id, UpdateRequestTypeDto dto, CancellationToken ct)
    {
        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var type = await db.RequestTypes.FirstOrDefaultAsync(t => t.Id == id, ct);
        if (type is null) return NotFound();

        type.Name = dto.Name;
        type.Description = dto.Description;
        type.UpdatedAt = DateTimeOffset.UtcNow;
        await db.SaveChangesAsync(ct);
        return Ok(ToResponse(type));
    }

    // No reactivation endpoint — deactivation is confirmed as a one-way transition.
    [HttpPost("{id:guid}/deactivate")]
    [Authorize(Policy = "CanAdminister")]
    public async Task<ActionResult<RequestTypeResponse>> Deactivate(Guid id, CancellationToken ct)
    {
        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var type = await db.RequestTypes.FirstOrDefaultAsync(t => t.Id == id, ct);
        if (type is null) return NotFound();

        type.IsActive = false;
        type.DeactivatedAt = DateTimeOffset.UtcNow;
        type.UpdatedAt = type.DeactivatedAt;
        await db.SaveChangesAsync(ct);
        return Ok(ToResponse(type));
    }
}
