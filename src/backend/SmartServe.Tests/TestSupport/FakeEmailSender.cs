using System.Collections.Concurrent;
using SmartServe.Api.Services.Email;

namespace SmartServe.Tests.TestSupport;

/// <summary>Test double for IEmailSender; optionally runs a callback during send to prove persistence ordering via independent DB reads.</summary>
public class FakeEmailSender : IEmailSender
{
    private readonly ConcurrentBag<EmailMessage> _sent = new();
    public IReadOnlyCollection<EmailMessage> Sent => _sent.ToArray();

    public bool AlwaysFail { get; set; }
    public Func<EmailMessage, Task>? OnSend { get; set; }

    public async Task<EmailSendResult> SendAsync(EmailMessage message, CancellationToken ct = default)
    {
        if (OnSend is not null) await OnSend(message);
        _sent.Add(message);
        return AlwaysFail
            ? new EmailSendResult(EmailSendOutcome.Failed, "SimulatedFailure")
            : new EmailSendResult(EmailSendOutcome.Accepted, "Accepted (fake sender)");
    }
}
