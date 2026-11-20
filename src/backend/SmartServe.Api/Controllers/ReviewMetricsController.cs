using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using SmartServe.Api.Services;

namespace SmartServe.Api.Controllers;

/// <summary>Reports the provisional NFR-003 90%-within-one-business-day metric (ARCH-COMP-007, TASK-012). Reused the audit-read policy: this is reporting over already-auditable status-change data, not request content. The response's <c>provisional</c> field is always true and must be surfaced to any consumer of this metric; all thresholds and the reporting-cohort definition (see <c>ReviewMetricsSummary</c>) are (proposed) pending stakeholder confirmation — see docs/decisions/access-request-contract.md.</summary>
[ApiController]
[Route("api/metrics")]
[Authorize(Policy = "CanAudit")]
public class ReviewMetricsController : ControllerBase
{
    private readonly ReviewMetricsService _metrics;

    public ReviewMetricsController(ReviewMetricsService metrics) => _metrics = metrics;

    [HttpGet("review")]
    public async Task<ActionResult<ReviewMetricsSummary>> GetReviewMetrics(CancellationToken ct)
        => Ok(await _metrics.ComputeSummaryAsync(ct));
}
