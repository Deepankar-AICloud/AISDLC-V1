namespace SmartServe.Api.Services.Email;

/// <summary>Development/Testing-only fallback when no real transport is configured; must never report Accepted.</summary>
public class UnconfiguredEmailSender : IEmailSender
{
    public Task<EmailSendResult> SendAsync(EmailMessage message, CancellationToken ct = default)
        => Task.FromResult(new EmailSendResult(EmailSendOutcome.NotConfigured, "EmailNotConfigured"));
}
