using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;
using SmartServe.Api.Dtos;
using SmartServe.Tests.TestSupport;
using Xunit;

namespace SmartServe.Tests;

/// <summary>Proves enums are serialized as JSON strings in an actual HTTP response (JsonStringEnumConverter).</summary>
public class EnumJsonSerializationTests : IAsyncLifetime
{
    private SmartServeWebApplicationFactory _factory = null!;
    private HttpClient _client = null!;

    public async Task InitializeAsync()
    {
        _factory = new SmartServeWebApplicationFactory();
        _client = _factory.CreateClient();
        await Task.CompletedTask;
    }

    public Task DisposeAsync()
    {
        _factory.Dispose();
        return Task.CompletedTask;
    }

    [Fact]
    public async Task Created_request_response_serializes_enums_as_strings()
    {
        await using var db = await _factory.Services.GetRequiredService<IDbContextFactory<SmartServeDbContext>>().CreateDbContextAsync();
        var typeId = (await db.RequestTypes.FirstAsync(t => t.Kind == RequestKind.Service)).Id;

        var msg = new HttpRequestMessage(HttpMethod.Post, "/api/requests");
        msg.Headers.Add("Authorization", SmartServeWebApplicationFactory.BearerFor("emp-json", Roles.Employee));
        msg.Content = JsonContent.Create(new CreateRequestDto(RequestKind.Service, typeId, "JSON check", "Verifying enum shape"), options: TestJson.Options);

        var res = await _client.SendAsync(msg);
        res.EnsureSuccessStatusCode();
        var raw = await res.Content.ReadAsStringAsync();

        using var doc = JsonDocument.Parse(raw);
        var root = doc.RootElement;
        Assert.Equal(JsonValueKind.String, root.GetProperty("kind").ValueKind);
        Assert.Equal("Service", root.GetProperty("kind").GetString());
        Assert.Equal(JsonValueKind.String, root.GetProperty("status").ValueKind);
        Assert.Equal("Submitted", root.GetProperty("status").GetString());

        // This exact captured shape is copied verbatim into the frontend fixture test (fixture-based, not live cross-stack).
    }
}
