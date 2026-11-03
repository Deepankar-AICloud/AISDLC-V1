namespace SmartServe.Api.Services.Email;

public record EmailMessage(string ToAddress, string Subject, string Body);

/// <summary>Distinguishes "no attempt possible" (NotConfigured) from a genuine send/delivery error (Failed).</summary>
public enum EmailSendOutcome
{
    Accepted,
    NotConfigured,
    Failed
}

/// <summary>Non-Accepted outcomes must always carry a Reason; callers persist Accepted/NotSent/Failed accordingly.</summary>
public record EmailSendResult(EmailSendOutcome Outcome, string? Reason);

public interface IEmailSender
{
    Task<EmailSendResult> SendAsync(EmailMessage message, CancellationToken ct = default);
}
