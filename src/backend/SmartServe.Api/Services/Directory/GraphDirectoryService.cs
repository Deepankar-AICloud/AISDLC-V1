using System.Net;
using System.Net.Http.Headers;
using System.Text.Json;
using Azure.Core;
using Azure.Identity;

namespace SmartServe.Api.Services.Directory;

/// <summary>(proposed) Production directory transport: Microsoft Graph users/{id} and users/{id}/manager via managed identity.</summary>
public class GraphDirectoryService : IDirectoryService
{
    private static readonly string[] Scopes = { "https://graph.microsoft.com/.default" };
    private readonly HttpClient _http;
    private readonly TokenCredential _credential;

    public GraphDirectoryService(HttpClient http)
    {
        _http = http;
        _http.BaseAddress ??= new Uri("https://graph.microsoft.com/v1.0/");
        _credential = new DefaultAzureCredential();
    }

    public Task<DirectoryUser?> GetUserAsync(string userId, CancellationToken ct = default)
        => GetAsync($"users/{Uri.EscapeDataString(userId)}?$select=id,displayName,mail,userPrincipalName", ct);

    public Task<DirectoryUser?> GetManagerAsync(string userId, CancellationToken ct = default)
        => GetAsync($"users/{Uri.EscapeDataString(userId)}/manager?$select=id,displayName,mail,userPrincipalName", ct);

    private async Task<DirectoryUser?> GetAsync(string path, CancellationToken ct)
    {
        try
        {
            var token = await _credential.GetTokenAsync(new TokenRequestContext(Scopes), ct);
            using var req = new HttpRequestMessage(HttpMethod.Get, path);
            req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token.Token);
            using var res = await _http.SendAsync(req, ct);

            if (res.StatusCode == HttpStatusCode.NotFound) return null;
            if (!res.IsSuccessStatusCode)
                throw new DirectoryUnavailableException($"Graph directory lookup failed with status {(int)res.StatusCode}");

            await using var stream = await res.Content.ReadAsStreamAsync(ct);
            using var doc = await JsonDocument.ParseAsync(stream, cancellationToken: ct);
            var root = doc.RootElement;
            var id = root.TryGetProperty("id", out var idEl) ? idEl.GetString() ?? string.Empty : string.Empty;
            var name = root.TryGetProperty("displayName", out var nameEl) ? nameEl.GetString() ?? string.Empty : string.Empty;
            var mail = root.TryGetProperty("mail", out var mailEl) ? mailEl.GetString() : null;
            var upn = root.TryGetProperty("userPrincipalName", out var upnEl) ? upnEl.GetString() : null;
            return new DirectoryUser(id, name, mail ?? upn);
        }
        catch (DirectoryUnavailableException)
        {
            throw;
        }
        catch (Exception ex)
        {
            throw new DirectoryUnavailableException($"Graph directory lookup threw: {ex.Message}", ex);
        }
    }
}
