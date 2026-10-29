using SmartServe.Api.Domain;
using SmartServe.Api.Services;
using Xunit;

namespace SmartServe.Tests;

// UT-001..UT-004 — verifies the configurable approval workflow (TASK-xxx).
public class WorkflowServiceTests
{
    private readonly WorkflowService _wf = new();

    [Theory]
    [InlineData(RequestCategory.ProductionAccess, true)]
    [InlineData(RequestCategory.DatabaseAccess, true)]
    [InlineData(RequestCategory.AzureAccess, true)]
    [InlineData(RequestCategory.VpnAccess, true)]
    [InlineData(RequestCategory.LaptopRequest, false)]
    [InlineData(RequestCategory.GeneralSupport, false)]
    public void RequiresSecurityReview_flags_sensitive_categories(
        RequestCategory category, bool expected)
    {
        Assert.Equal(expected, _wf.RequiresSecurityReview(category));
    }

    [Fact]
    public void Manager_approval_routes_to_security_when_sensitive()
    {
        var req = new AccessRequest { RequiresSecurityReview = true };
        Assert.Equal(RequestStatus.SecurityApproval, _wf.Advance(req, "Manager", true));
    }

    [Fact]
    public void Manager_approval_skips_security_when_not_sensitive()
    {
        var req = new AccessRequest { RequiresSecurityReview = false };
        Assert.Equal(RequestStatus.ItProcessing, _wf.Advance(req, "Manager", true));
    }

    [Fact]
    public void Rejection_at_any_stage_sets_rejected()
    {
        var req = new AccessRequest { RequiresSecurityReview = true };
        Assert.Equal(RequestStatus.Rejected, _wf.Advance(req, "Manager", false));
    }

    [Fact]
    public void It_processing_leads_to_provisioned()
    {
        var req = new AccessRequest();
        Assert.Equal(RequestStatus.Provisioned, _wf.Advance(req, "IT", true));
    }

    [Theory]
    [InlineData(RequestStatus.Submitted, "Manager")]
    [InlineData(RequestStatus.SecurityApproval, "Security")]
    [InlineData(RequestStatus.ItProcessing, "IT")]
    [InlineData(RequestStatus.Closed, null)]
    public void CurrentStage_reflects_status(RequestStatus status, string? expected)
    {
        var req = new AccessRequest { Status = status };
        Assert.Equal(expected, _wf.CurrentStage(req));
    }
}
