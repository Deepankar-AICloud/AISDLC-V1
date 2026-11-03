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

/// <summary>Auditor: read-only over all requests with paginated history; SecurityReviewer: read-only over access requests only, no decisions.</summary>
public class RoleScopeTests : IAsyncLifetime
{
    private SmartServeWebApplicationFactory _factory = null!;
    private HttpClient _client = null!;
    private Guid _accessTypeId;
    private Guid _serviceTypeId;
    private Guid _accessRequestId;
    private Guid _serviceRequestId;

    public async Task InitializeAsync()
    {
        _factory = new SmartServeWebApplicationFactory();
        _client = _factory.CreateClient();

        await using var db = await DbFactory().CreateDbContextAsync();
        _accessTypeId = (await db.RequestTypes.FirstAsync(t => t.Kind == RequestKind.Access)).Id;
        _serviceTypeId = (await db.RequestTypes.FirstAsync(t => t.Kind == RequestKind.Service)).Id;

        _accessRequestId = (await CreateAsync(RequestKind.Access, _accessTypeId, "emp-role-access")).Id;
        _serviceRequestId = (await CreateAsync(RequestKind.Service, _serviceTypeId, "emp-role-service")).Id;
    }

    public Task DisposeAsync()
    {
        _factory.Dispose();
        return Task.CompletedTask;
    }

    private IDbContextFactory<SmartServeDbContext> DbFactory() =>
        _factory.Services.GetRequiredService<IDbContextFactory<SmartServeDbContext>>();

    private HttpRequestMessage Req(HttpMethod method, string path, string userId, string role, object? body = null)
    {
        var msg = new HttpRequestMessage(method, path);
        msg.Headers.Add("Authorization", SmartServeWebApplicationFactory.BearerFor(userId, role));
        if (body is not null) msg.Content = JsonContent.Create(body, options: TestJson.Options);
        return msg;
    }

    private async Task<RequestResponse> CreateAsync(RequestKind kind, Guid typeId, string employeeId)
    {
        var res = await _client.SendAsync(Req(HttpMethod.Post, "/api/requests", employeeId, Roles.Employee,
            new CreateRequestDto(kind, typeId, "Title", "Description")));
        res.EnsureSuccessStatusCode();
        return (await res.Content.ReadFromJsonAsync<RequestResponse>(TestJson.Options))!;
    }

    [Fact]
    public async Task Auditor_sees_both_access_and_service_requests_with_full_paginated_history()
    {
        var listRes = await _client.SendAsync(Req(HttpMethod.Get, "/api/audit/requests?page=1&pageSize=1", "auditor-x", Roles.Auditor));
        listRes.EnsureSuccessStatusCode();
        var page1 = await listRes.Content.ReadFromJsonAsync<PagedResult<RequestResponse>>(TestJson.Options);
        Assert.NotNull(page1);
        Assert.Equal(1, page1!.PageSize);
        Assert.True(page1.TotalCount >= 2);

        var fullRes = await _client.SendAsync(Req(HttpMethod.Get, "/api/audit/requests?page=1&pageSize=100", "auditor-x", Roles.Auditor));
        var full = await fullRes.Content.ReadFromJsonAsync<PagedResult<RequestResponse>>(TestJson.Options);
        Assert.Contains(full!.Items, r => r.Id == _accessRequestId);
        Assert.Contains(full.Items, r => r.Id == _serviceRequestId);

        var historyRes = await _client.SendAsync(Req(HttpMethod.Get, $"/api/audit/requests/{_accessRequestId}/history", "auditor-x", Roles.Auditor));
        historyRes.EnsureSuccessStatusCode();
        var history = await historyRes.Content.ReadFromJsonAsync<PagedResult<AuditEntryResponse>>(TestJson.Options);
        Assert.True(history!.TotalCount >= 1);
        Assert.Contains(history.Items, a => a.NewStatus == RequestStatus.Submitted && a.OldStatus == null);
    }

    public static IEnumerable<object[]> MutatingEndpoints()
    {
        yield return new object[] { HttpMethod.Post, "/api/requests", true };
        yield return new object[] { HttpMethod.Post, "/api/requests/00000000-0000-0000-0000-000000000000/decision", true };
        yield return new object[] { HttpMethod.Post, "/api/requests/00000000-0000-0000-0000-000000000000/fulfil", true };
        yield return new object[] { HttpMethod.Post, "/api/requests/00000000-0000-0000-0000-000000000000/retry-routing", true };
        yield return new object[] { HttpMethod.Post, "/api/request-types", true };
        yield return new object[] { HttpMethod.Put, "/api/request-types/00000000-0000-0000-0000-000000000000", true };
        yield return new object[] { HttpMethod.Post, "/api/request-types/00000000-0000-0000-0000-000000000000/deactivate", false };
    }

    [Theory]
    [MemberData(nameof(MutatingEndpoints))]
    public async Task Auditor_write_attempts_are_rejected_even_combined_with_another_role(HttpMethod method, string path, bool withBody)
    {
        object? body = withBody ? new { } : null;
        var combinedRoleHeader = $"{Roles.Auditor},{Roles.AppAdmin}"; // Auditor combined with a normally-privileged role
        var msg = new HttpRequestMessage(method, path);
        msg.Headers.TryAddWithoutValidation("Authorization", $"Bearer test:auditor-combo:{combinedRoleHeader}");
        if (body is not null) msg.Content = JsonContent.Create(body);

        var res = await _client.SendAsync(msg);
        Assert.Equal(HttpStatusCode.Forbidden, res.StatusCode);
    }

    [Fact]
    public async Task SecurityReviewer_sees_access_requests_only_not_service_requests()
    {
        var res = await _client.SendAsync(Req(HttpMethod.Get, "/api/security/access-requests?pageSize=100", "sec-1", Roles.SecurityReviewer));
        res.EnsureSuccessStatusCode();
        var page = await res.Content.ReadFromJsonAsync<PagedResult<RequestResponse>>(TestJson.Options);

        Assert.Contains(page!.Items, r => r.Id == _accessRequestId);
        Assert.DoesNotContain(page.Items, r => r.Id == _serviceRequestId);
        Assert.All(page.Items, r => Assert.Equal(RequestKind.Access, r.Kind));
    }

    [Fact]
    public async Task SecurityReviewer_cannot_approve_or_reject()
    {
        var res = await _client.SendAsync(Req(HttpMethod.Post, $"/api/requests/{_accessRequestId}/decision", "sec-2", Roles.SecurityReviewer,
            new DecisionDto(true, null)));
        Assert.Equal(HttpStatusCode.Forbidden, res.StatusCode);
    }
}
