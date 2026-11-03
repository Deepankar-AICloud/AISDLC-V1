using SmartServe.Api.Domain;

namespace SmartServe.Api.Services.Email;

/// <summary>Single shared email content builder used by every notification — not duplicated per controller.</summary>
public static class EmailTemplates
{
    public static (string Subject, string Body) Build(NotificationTemplate template, PortalRequest request) => template switch
    {
        NotificationTemplate.RequesterSubmitted => (
            $"Your request \"{request.Title}\" was submitted",
            $"Hello,\n\nYour {request.Kind} request \"{request.Title}\" has been submitted and is now in status Submitted.\n\nSmartServe"),
        NotificationTemplate.RequesterUnderReview => (
            $"Your request \"{request.Title}\" is under review",
            $"Hello,\n\nYour request \"{request.Title}\" is now under review by your manager.\n\nSmartServe"),
        NotificationTemplate.RequesterApproved => (
            $"Your request \"{request.Title}\" was approved",
            $"Hello,\n\nYour request \"{request.Title}\" has been approved and will be fulfilled shortly.\n\nSmartServe"),
        NotificationTemplate.RequesterRejected => (
            $"Your request \"{request.Title}\" was rejected",
            $"Hello,\n\nYour request \"{request.Title}\" has been rejected by your manager.\n\nSmartServe"),
        NotificationTemplate.RequesterFulfilled => (
            $"Your request \"{request.Title}\" was fulfilled",
            $"Hello,\n\nYour request \"{request.Title}\" has been fulfilled.\n\nSmartServe"),
        // Distinct manager-facing template — never reuses the requester wording.
        NotificationTemplate.ManagerWaitingApproval => (
            $"Approval needed: \"{request.Title}\"",
            $"Hello,\n\nA request from one of your reports, \"{request.Title}\", is waiting for your approval in SmartServe.\n\nSmartServe"),
        _ => throw new ArgumentOutOfRangeException(nameof(template))
    };
}
