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

/// <summary>TASK-011: manager team-scope tests — correct filtering, unauthorized access, and unresolved/unavailable team scope.</summary>
public class TeamRequestsTests : IAsyncLifetime
{
    private SmartServeWebApplicationFactory _factory = null!;
    private HttpClient _client = null!;
    private Guid _accessTypeId;

    public async Task InitializeAsync()
    {
        _factory = new SmartServeWebApplicationFactory();
        _client = _factory.CreateClient();

        await using var db = await DbFactory().CreateDbContextAsync();
        _accessTypeId = (await db.RequestTypes.FirstAsync(t => t.Kind == RequestKind.Access)).Id;

        _factory.Directory.AddUser(new("manager-a", "Manager A", "a@contoso.example"));
        _factory.Directory.AddUser(new("manager-b", "Manager B", "b@contoso.example"));
        _factory.Directory.SetManager("emp-a1", "manager-a");
        _factory.Directory.SetManager("emp-b1", "manager-b");
        // emp-orphan has no resolvable manager: request should stay Submitted with no ManagerId, invisible to every manager.
    }

    public Task DisposeAsync()
    {
        _factory.Dispose();
        return Task.CompletedTask;
    }

    private IDbContextFactory<SmartServeDbContext> DbFactory() =>
        _factory.Services.GetRequiredService<IDbContextFactory<SmartServeDbContext>>();

    private async Task<Guid> SubmitAsync(string employeeId)
    {
        using var create = new HttpRequestMessage(HttpMethod.Post, "/api/requests");
        create.Headers.Add("Authorization", SmartServeWebApplicationFactory.BearerFor(employeeId, Roles.Employee));
        create.Content = JsonContent.Create(new CreateRequestDto(RequestKind.Access, _accessTypeId, "Need access", "desc"));
        var res = await _client.SendAsync(create);
        res.EnsureSuccessStatusCode();
        var body = await res.Content.ReadFromJsonAsync<RequestResponse>(TestJson.Options);
        return body!.Id;
    }

    [Fact]
    public async Task Manager_sees_only_requests_resolved_to_their_own_team()
    {
        var requestA = await SubmitAsync("emp-a1");
        var requestB = await SubmitAsync("emp-b1");

        using var teamA = new HttpRequestMessage(HttpMethod.Get, "/api/team/requests");
        teamA.Headers.Add("Authorization", SmartServeWebApplicationFactory.BearerFor("manager-a", Roles.Manager));
        var resA = await _client.SendAsync(teamA);
        resA.EnsureSuccessStatusCode();
        var pageA = await resA.Content.ReadFromJsonAsync<PagedResult<RequestResponse>>(TestJson.Options);

        Assert.Contains(pageA!.Items, r => r.Id == requestA);
        Assert.DoesNotContain(pageA.Items, r => r.Id == requestB);
    }

    [Fact]
    public async Task Employee_cannot_access_the_team_endpoint()
    {
        using var req = new HttpRequestMessage(HttpMethod.Get, "/api/team/requests");
        req.Headers.Add("Authorization", SmartServeWebApplicationFactory.BearerFor("emp-a1", Roles.Employee));
        var res = await _client.SendAsync(req);
        Assert.Equal(HttpStatusCode.Forbidden, res.StatusCode);
    }

    [Fact]
    public async Task Requests_with_unresolved_manager_scope_are_denied_to_every_manager()
    {
        var orphanId = await SubmitAsync("emp-orphan");

        using var teamA = new HttpRequestMessage(HttpMethod.Get, "/api/team/requests");
        teamA.Headers.Add("Authorization", SmartServeWebApplicationFactory.BearerFor("manager-a", Roles.Manager));
        var resA = await _client.SendAsync(teamA);
        var pageA = await resA.Content.ReadFromJsonAsync<PagedResult<RequestResponse>>(TestJson.Options);
        Assert.DoesNotContain(pageA!.Items, r => r.Id == orphanId);

        using var teamB = new HttpRequestMessage(HttpMethod.Get, "/api/team/requests");
        teamB.Headers.Add("Authorization", SmartServeWebApplicationFactory.BearerFor("manager-b", Roles.Manager));
        var resB = await _client.SendAsync(teamB);
        var pageB = await resB.Content.ReadFromJsonAsync<PagedResult<RequestResponse>>(TestJson.Options);
        Assert.DoesNotContain(pageB!.Items, r => r.Id == orphanId);
    }

    [Fact]
    public async Task Team_scope_reflects_a_manager_reassignment_immediately()
    {
        var requestId = await SubmitAsync("emp-a1");

        // emp-a1 is reassigned from manager-a to manager-b after submission; the stored PortalRequest.ManagerId
        // snapshot (set once at submission for notification routing) must not grant manager-a continued access.
        _factory.Directory.SetManager("emp-a1", "manager-b");

        using var teamA = new HttpRequestMessage(HttpMethod.Get, "/api/team/requests");
        teamA.Headers.Add("Authorization", SmartServeWebApplicationFactory.BearerFor("manager-a", Roles.Manager));
        var resA = await _client.SendAsync(teamA);
        var pageA = await resA.Content.ReadFromJsonAsync<PagedResult<RequestResponse>>(TestJson.Options);
        Assert.DoesNotContain(pageA!.Items, r => r.Id == requestId);

        using var teamB = new HttpRequestMessage(HttpMethod.Get, "/api/team/requests");
        teamB.Headers.Add("Authorization", SmartServeWebApplicationFactory.BearerFor("manager-b", Roles.Manager));
        var resB = await _client.SendAsync(teamB);
        var pageB = await resB.Content.ReadFromJsonAsync<PagedResult<RequestResponse>>(TestJson.Options);
        Assert.Contains(pageB!.Items, r => r.Id == requestId);
    }

    [Fact]
    public async Task Team_scope_is_denied_when_the_directory_cannot_verify_it()
    {
        await SubmitAsync("emp-a1");
        _factory.Directory.MarkBroken("manager-a");

        using var req = new HttpRequestMessage(HttpMethod.Get, "/api/team/requests");
        req.Headers.Add("Authorization", SmartServeWebApplicationFactory.BearerFor("manager-a", Roles.Manager));
        var res = await _client.SendAsync(req);

        Assert.Equal(HttpStatusCode.Forbidden, res.StatusCode);
    }

    [Fact]
    public async Task Team_requests_are_paginated_beyond_the_default_page_size()
    {
        for (var i = 0; i < 55; i++)
            await SubmitAsync("emp-a1");

        using var firstPage = new HttpRequestMessage(HttpMethod.Get, "/api/team/requests");
        firstPage.Headers.Add("Authorization", SmartServeWebApplicationFactory.BearerFor("manager-a", Roles.Manager));
        var res1 = await _client.SendAsync(firstPage);
        var page1 = await res1.Content.ReadFromJsonAsync<PagedResult<RequestResponse>>(TestJson.Options);
        Assert.Equal(55, page1!.TotalCount);
        Assert.Equal(50, page1.Items.Count);

        using var secondPage = new HttpRequestMessage(HttpMethod.Get, "/api/team/requests?page=2&pageSize=50");
        secondPage.Headers.Add("Authorization", SmartServeWebApplicationFactory.BearerFor("manager-a", Roles.Manager));
        var res2 = await _client.SendAsync(secondPage);
        var page2 = await res2.Content.ReadFromJsonAsync<PagedResult<RequestResponse>>(TestJson.Options);
        Assert.Equal(5, page2!.Items.Count);
        Assert.Empty(page2.Items.Select(r => r.Id).Intersect(page1.Items.Select(r => r.Id)));
    }
}
