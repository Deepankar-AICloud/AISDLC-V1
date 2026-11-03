using System.Net.Http.Headers;
using System.Net.Http.Json;
using Azure.Core;
using Azure.Identity;
using Microsoft.Extensions.Configuration;

namespace SmartServe.Api.Services.Email;

/// <summary>(proposed) Production email transport: Microsoft Graph sendMail using the API's managed identity.</summary>
public class GraphEmailSender : IEmailSender
{
    private static readonly string[] Scopes = { "https://graph.microsoft.com/.default" };
    private readonly HttpClient _http;
    private readonly TokenCredential _credential;
    private readonly string _senderUserId;

    public GraphEmailSender(HttpClient http, IConfiguration config)
    {
        _http = http;
        _http.BaseAddress ??= new Uri("https://graph.microsoft.com/v1.0/");
        _credential = new DefaultAzureCredential();
        _senderUserId = config["Graph:SenderUserId"] ?? "smartserve-notifications@contoso.example";
    }

    public async Task<EmailSendResult> SendAsync(EmailMessage message, CancellationToken ct = default)
    {
        try
        {
            var token = await _credential.GetTokenAsync(new TokenRequestContext(Scopes), ct);
            var payload = new
            {
                message = new
                {
                    subject = message.Subject,
                    body = new { contentType = "Text", content = message.Body },
                    toRecipients = new[] { new { emailAddress = new { address = message.ToAddress } } }
                },
                saveToSentItems = false
            };

            using var req = new HttpRequestMessage(HttpMethod.Post, $"users/{Uri.EscapeDataString(_senderUserId)}/sendMail")
            {
                Content = JsonContent.Create(payload)
            };
            req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token.Token);

            using var res = await _http.SendAsync(req, ct);
            return res.IsSuccessStatusCode
                ? new EmailSendResult(EmailSendOutcome.Accepted, "Accepted by Graph sendMail (accepted for delivery, not proof of delivery)")
                : new EmailSendResult(EmailSendOutcome.Failed, $"GraphSendMailFailed:{(int)res.StatusCode}");
        }
        catch (Exception ex)
        {
            return new EmailSendResult(EmailSendOutcome.Failed, $"GraphSendMailException:{ex.Message}");
        }
    }
}
