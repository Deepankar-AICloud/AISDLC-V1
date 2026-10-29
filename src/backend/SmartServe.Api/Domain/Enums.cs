namespace SmartServe.Api.Domain;

/// <summary>Application roles. Authorization is enforced server-side via policies.</summary>
public static class Roles
{
    public const string Employee = "Employee";
    public const string Manager = "Manager";
    public const string SecurityReviewer = "SecurityReviewer";
    public const string ItAdmin = "ItAdmin";
    public const string AppAdmin = "AppAdmin";
    public const string Auditor = "Auditor";

    public static readonly string[] All =
    {
        Employee, Manager, SecurityReviewer, ItAdmin, AppAdmin, Auditor
    };
}

/// <summary>Lifecycle states for an access/service request (maps to the workflow).</summary>
public enum RequestStatus
{
    Draft,
    Submitted,
    ManagerApproval,
    SecurityApproval,
    ItProcessing,
    Provisioned,
    AwaitingConfirmation,
    Closed,
    Rejected
}

/// <summary>Categories of IT service / access request.</summary>
public enum RequestCategory
{
    GitHubAccess,
    AzureAccess,
    VpnAccess,
    ApplicationAccess,
    DatabaseAccess,
    ProductionAccess,
    SoftwareInstallation,
    LaptopRequest,
    HardwareRequest,
    PasswordSupport,
    GeneralSupport
}
