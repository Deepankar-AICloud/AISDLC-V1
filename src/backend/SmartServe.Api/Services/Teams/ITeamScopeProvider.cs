using SmartServe.Api.Services.Directory;

namespace SmartServe.Api.Services.Teams;

/// <summary>Result of resolving a manager's current team scope. <see cref="MemberIds"/> is null when scope could not be verified (directory outage) — callers must deny access rather than guess (ARCH-COMP-004, fail-closed).</summary>
public record TeamScopeResult(IReadOnlyCollection<string>? MemberIds)
{
    public bool IsResolved => MemberIds is not null;
}

/// <summary>Swappable abstraction (ARCH-COMP-004, Team Scope Service) over whatever is the authoritative source for employee-manager relationships. Resolves scope at request time — never from a cached/stored field — so a manager reassignment takes effect immediately and a former manager loses access as soon as the org record changes.</summary>
public interface ITeamScopeProvider
{
    Task<TeamScopeResult> ResolveTeamScopeAsync(string managerId, CancellationToken ct = default);
}

/// <summary>Default implementation backed by <see cref="IDirectoryService"/> (HR/Org Directory integration, proposed). Swappable: replace this registration if the authoritative team-relationship source changes.</summary>
public class DirectoryTeamScopeProvider : ITeamScopeProvider
{
    private readonly IDirectoryService _directory;

    public DirectoryTeamScopeProvider(IDirectoryService directory) => _directory = directory;

    public async Task<TeamScopeResult> ResolveTeamScopeAsync(string managerId, CancellationToken ct = default)
    {
        try
        {
            var reports = await _directory.GetDirectReportIdsAsync(managerId, ct);
            return new TeamScopeResult(reports);
        }
        catch (DirectoryUnavailableException)
        {
            // Fail closed: an outage must deny access, never fall back to a stale/guessed scope.
            return new TeamScopeResult(null);
        }
    }
}
