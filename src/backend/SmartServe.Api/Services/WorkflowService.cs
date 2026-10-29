using SmartServe.Api.Domain;

namespace SmartServe.Api.Services;

/// <summary>
/// Configurable approval workflow. Different request categories follow
/// different approval paths (prompt sections 3 & 19). Kept data-driven so the
/// chain can be extended without changing controllers.
/// </summary>
public class WorkflowService
{
    // Categories that always require a security review step.
    private static readonly HashSet<RequestCategory> SecuritySensitive = new()
    {
        RequestCategory.ProductionAccess,
        RequestCategory.DatabaseAccess,
        RequestCategory.AzureAccess,
        RequestCategory.VpnAccess
    };

    public bool RequiresSecurityReview(RequestCategory category)
        => SecuritySensitive.Contains(category);

    /// <summary>Compute the next status after an approval/processing decision.</summary>
    public RequestStatus Advance(AccessRequest req, string stage, bool approved)
    {
        if (!approved)
            return RequestStatus.Rejected;

        return stage switch
        {
            "Manager" => req.RequiresSecurityReview
                ? RequestStatus.SecurityApproval
                : RequestStatus.ItProcessing,
            "Security" => RequestStatus.ItProcessing,
            "IT" => RequestStatus.Provisioned,
            _ => req.Status
        };
    }

    /// <summary>The stage that is currently awaiting a decision for this request.</summary>
    public string? CurrentStage(AccessRequest req) => req.Status switch
    {
        RequestStatus.Submitted or RequestStatus.ManagerApproval => "Manager",
        RequestStatus.SecurityApproval => "Security",
        RequestStatus.ItProcessing => "IT",
        _ => null
    };
}
