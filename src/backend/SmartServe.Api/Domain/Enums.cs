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

/// <summary>Distinguishes the two confirmed request flows that share one entity (PortalRequest).</summary>
public enum RequestKind
{
    Access,
    Service
}

/// <summary>Shared lifecycle for both access and service requests.</summary>
public enum RequestStatus
{
    Submitted,
    UnderReview,
    Approved,
    Rejected,
    Fulfilled
}

/// <summary>Accepted = Graph sendMail accepted the message for delivery (not proof of delivery).</summary>
public enum NotificationStatus
{
    Pending,
    Accepted,
    NotSent,
    Failed
}

/// <summary>Identifies which email template/content variant a notification uses.</summary>
public enum NotificationTemplate
{
    RequesterSubmitted,
    RequesterUnderReview,
    RequesterApproved,
    RequesterRejected,
    RequesterFulfilled,
    ManagerWaitingApproval
}
