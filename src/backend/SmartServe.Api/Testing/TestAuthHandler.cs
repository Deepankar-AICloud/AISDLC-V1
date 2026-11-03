using System.Security.Claims;
using System.Text.Encodings.Web;
using Microsoft.AspNetCore.Authentication;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace SmartServe.Api.Testing;

/// <summary>Test-only auth scheme (Testing environment) replacing Entra ID JWT bearer for integration tests.</summary>
public class TestAuthHandler : AuthenticationHandler<AuthenticationSchemeOptions>
{
    public const string SchemeName = "TestScheme";
    private const string Prefix = "Bearer test:";

    public TestAuthHandler(IOptionsMonitor<AuthenticationSchemeOptions> options, ILoggerFactory logger,
        UrlEncoder encoder) : base(options, logger, encoder) { }

    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        if (!Request.Headers.TryGetValue("Authorization", out var header) || string.IsNullOrEmpty(header))
            return Task.FromResult(AuthenticateResult.NoResult());

        var value = header.ToString();
        if (!value.StartsWith(Prefix, StringComparison.Ordinal))
            return Task.FromResult(AuthenticateResult.Fail("Invalid or unrecognized test token."));

        var payload = value[Prefix.Length..];
        var parts = payload.Split(':', 2);
        var userId = parts[0];
        var roles = parts.Length > 1 ? parts[1].Split(',', StringSplitOptions.RemoveEmptyEntries) : Array.Empty<string>();

        var claims = new List<Claim> { new("oid", userId), new(ClaimTypes.NameIdentifier, userId) };
        claims.AddRange(roles.Select(r => new Claim(ClaimTypes.Role, r)));

        var identity = new ClaimsIdentity(claims, SchemeName);
        var principal = new ClaimsPrincipal(identity);
        var ticket = new AuthenticationTicket(principal, SchemeName);
        return Task.FromResult(AuthenticateResult.Success(ticket));
    }
}
