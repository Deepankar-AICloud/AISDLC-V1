using System.Net;
using System.Net.Http.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;
using SmartServe.Api.Dtos;
using SmartServe.Tests.TestSupport;
using Xunit;

namespace SmartServe.Tests;

/// <summary>Data-driven test over every endpoint (incl. /health): no token/invalid token rejected, valid role succeeds (status codes (proposed)).</summary>
public class EndpointAuthorizationTests : IAsyncLifetime
{
    private readonly SmartServeWebApplicationFactory _factory = new();
    private HttpClient _client = null!;
    private Guid _accessTypeId;
    private Guid _serviceTypeId;
    private Guid _editableTypeId;
    private Guid _underReviewRequestId;
    private Guid _approvedRequestId;

    public async Task InitializeAsync()
    {
        _client = _factory.CreateClient();

        await using var db = await _factory.Services.GetRequiredService<IDbContextFactory<SmartServeDbContext>>().CreateDbContextAsync();
        _accessTypeId = (await db.RequestTypes.FirstAsync(t => t.Kind == RequestKind.Access)).Id;
        _serviceTypeId = (await db.RequestTypes.FirstAsync(t => t.Kind == RequestKind.Service)).Id;

        // Dedicated type for the edit/deactivate cases so they don't interact with the "Create request type" case.
        var editable = new RequestType { Kind = RequestKind.Service, Name = "Editable Type", Description = "For edit/deactivate tests" };
        db.RequestTypes.Add(editable);
        await db.SaveChangesAsync();
        _editableTypeId = editable.Id;

        _factory.Directory.AddUser(new("manager-1", "Manager One", "manager1@contoso.example"));
        _factory.Directory.SetManager("employee-1", "manager-1");
        _factory.Directory.SetManager("employee-2", "manager-1");

        _underReviewRequestId = await CreateAccessRequestInStatusAsync("employee-1", RequestStatus.UnderReview);
        _approvedRequestId = await CreateAccessRequestInStatusAsync("employee-2", RequestStatus.Approved);
    }

    public Task DisposeAsync()
    {
        _factory.Dispose();
        return Task.CompletedTask;
    }

    private async Task<Guid> CreateAccessRequestInStatusAsync(string employeeId, RequestStatus target)
    {
        _factory.Directory.AddUser(new(employeeId, employeeId, $"{employeeId}@contoso.example"));
        using var create = new HttpRequestMessage(HttpMethod.Post, "/api/requests");
        create.Headers.Add("Authorization", SmartServeWebApplicationFactory.BearerFor(employeeId, Roles.Employee));
        create.Content = JsonContent.Create(new CreateRequestDto(RequestKind.Access, _accessTypeId, "Need access", "Please grant access"));
        var created = await _client.SendAsync(create);
        created.EnsureSuccessStatusCode();
        var body = await created.Content.ReadFromJsonAsync<RequestResponse>(TestJson.Options);
        var id = body!.Id;

        if (target == RequestStatus.Approved)
        {
            using var decide = new HttpRequestMessage(HttpMethod.Post, $"/api/requests/{id}/decision");
            decide.Headers.Add("Authorization", SmartServeWebApplicationFactory.BearerFor("manager-1", Roles.Manager));
            decide.Content = JsonContent.Create(new DecisionDto(true, "approved"));
            (await _client.SendAsync(decide)).EnsureSuccessStatusCode();
        }
        return id;
    }

    private record Case(string Name, HttpMethod Method, Func<string> Path, Func<object?>? Body,
        string RequiredRole, string RequiredUserId, HttpStatusCode ExpectedSuccess);

    [Fact]
    public async Task Every_endpoint_enforces_authentication_and_role_then_succeeds()
    {
        var cases = new List<Case>
        {
            new("Health", HttpMethod.Get, () => "/health", null, Roles.Employee, "any-user", HttpStatusCode.OK),
            new("Create access request", HttpMethod.Post, () => "/api/requests", () =>
                new CreateRequestDto(RequestKind.Service, _serviceTypeId, "New laptop", "Need a laptop"),
                Roles.Employee, "emp-create", HttpStatusCode.Created),
            new("List own requests", HttpMethod.Get, () => "/api/requests", null, Roles.Employee, "emp-create", HttpStatusCode.OK),
            new("Request by id", HttpMethod.Get, () => $"/api/requests/{_underReviewRequestId}", null,
                Roles.Employee, "employee-1", HttpStatusCode.OK),
            new("Manager decision", HttpMethod.Post, () => $"/api/requests/{_underReviewRequestId}/decision",
                () => new DecisionDto(true, "ok"), Roles.Manager, "manager-1", HttpStatusCode.OK),
            new("IT fulfil", HttpMethod.Post, () => $"/api/requests/{_approvedRequestId}/fulfil", null,
                Roles.ItAdmin, "it-admin-1", HttpStatusCode.OK),
            new("Retry routing", HttpMethod.Post, () => $"/api/requests/{_approvedRequestId}/retry-routing", null,
                Roles.ItAdmin, "it-admin-1", HttpStatusCode.OK),
            new("Auditor list all", HttpMethod.Get, () => "/api/audit/requests", null, Roles.Auditor, "auditor-1", HttpStatusCode.OK),
            new("Auditor history", HttpMethod.Get, () => $"/api/audit/requests/{_underReviewRequestId}/history", null,
                Roles.Auditor, "auditor-1", HttpStatusCode.OK),
            new("Security reviewer list", HttpMethod.Get, () => "/api/security/access-requests", null,
                Roles.SecurityReviewer, "security-1", HttpStatusCode.OK),
            new("List request types", HttpMethod.Get, () => "/api/request-types", null, Roles.Employee, "emp-create", HttpStatusCode.OK),
            new("Create request type", HttpMethod.Post, () => "/api/request-types", () =>
                new CreateRequestTypeDto(RequestKind.Service, "Monitor Request", "Extra monitor"),
                Roles.AppAdmin, "app-admin-1", HttpStatusCode.Created),
            new("Edit request type", HttpMethod.Put, () => $"/api/request-types/{_editableTypeId}", () =>
                new UpdateRequestTypeDto("Editable Type (renamed)", "Updated description"),
                Roles.AppAdmin, "app-admin-1", HttpStatusCode.OK),
            new("Deactivate request type", HttpMethod.Post, () => $"/api/request-types/{_editableTypeId}/deactivate", null,
                Roles.AppAdmin, "app-admin-1", HttpStatusCode.OK),
        };

        var failures = new List<string>();
        foreach (var c in cases)
        {
            using var noToken = new HttpRequestMessage(c.Method, c.Path());
            var noTokenRes = await _client.SendAsync(noToken);
            if (noTokenRes.StatusCode != HttpStatusCode.Unauthorized)
                failures.Add($"{c.Name}: no-token expected 401 got {(int)noTokenRes.StatusCode}");

            using var invalidToken = new HttpRequestMessage(c.Method, c.Path());
            invalidToken.Headers.Add("Authorization", "Bearer invalid-token");
            var invalidRes = await _client.SendAsync(invalidToken);
            if (invalidRes.StatusCode != HttpStatusCode.Unauthorized)
                failures.Add($"{c.Name}: invalid-token expected 401 got {(int)invalidRes.StatusCode}");

            using var valid = new HttpRequestMessage(c.Method, c.Path());
            valid.Headers.Add("Authorization", SmartServeWebApplicationFactory.BearerFor(c.RequiredUserId, c.RequiredRole));
            if (c.Body is not null) valid.Content = JsonContent.Create(c.Body());
            var validRes = await _client.SendAsync(valid);
            if (validRes.StatusCode != c.ExpectedSuccess)
            {
                var text = await validRes.Content.ReadAsStringAsync();
                failures.Add($"{c.Name}: valid-token expected {(int)c.ExpectedSuccess} got {(int)validRes.StatusCode} ({text})");
            }
        }

        Assert.True(failures.Count == 0, string.Join("\n", failures));
    }
}
