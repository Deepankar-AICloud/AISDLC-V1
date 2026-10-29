using System.Net;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

namespace SmartServe.Tests;

// FT-level integration tests against the real pipeline using the in-memory DB.
public class ApiIntegrationTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly WebApplicationFactory<Program> _factory;

    public ApiIntegrationTests(WebApplicationFactory<Program> factory)
        => _factory = factory;

    [Fact]
    public async Task Health_endpoint_is_anonymous_and_healthy()
    {
        var client = _factory.CreateClient();
        var res = await client.GetAsync("/health");
        Assert.Equal(HttpStatusCode.OK, res.StatusCode);
    }

    [Fact]
    public async Task Requests_endpoint_requires_authentication()
    {
        var client = _factory.CreateClient();
        var res = await client.GetAsync("/api/requests");
        // Server-side authorization: unauthenticated requests are rejected.
        Assert.Equal(HttpStatusCode.Unauthorized, res.StatusCode);
    }
}
