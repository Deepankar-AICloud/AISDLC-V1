using System.Collections.Concurrent;
using SmartServe.Api.Services.Directory;

namespace SmartServe.Tests.TestSupport;

/// <summary>Configurable directory double: resolves users/managers, or throws DirectoryUnavailableException for ids marked "broken".</summary>
public class FakeDirectoryService : IDirectoryService
{
    private readonly ConcurrentDictionary<string, DirectoryUser> _users = new();
    private readonly ConcurrentDictionary<string, string> _managerOf = new();
    private readonly ConcurrentDictionary<string, bool> _broken = new();

    public void AddUser(DirectoryUser user) => _users[user.Id] = user;
    public void SetManager(string userId, string managerId) => _managerOf[userId] = managerId;
    public void MarkBroken(string userId) => _broken[userId] = true;

    /// <summary>Test seam only: invoked at the start of GetManagerAsync, to let tests force overlapping calls to race.</summary>
    public Func<Task>? OnGetManager { get; set; }

    public Task<DirectoryUser?> GetUserAsync(string userId, CancellationToken ct = default)
    {
        if (_broken.ContainsKey(userId))
            throw new DirectoryUnavailableException($"Simulated directory outage for {userId}");
        return Task.FromResult(_users.TryGetValue(userId, out var u) ? u : null);
    }

    public async Task<DirectoryUser?> GetManagerAsync(string userId, CancellationToken ct = default)
    {
        if (OnGetManager is not null) await OnGetManager();
        if (_broken.ContainsKey(userId))
            throw new DirectoryUnavailableException($"Simulated directory outage resolving manager of {userId}");
        if (_managerOf.TryGetValue(userId, out var managerId) && _users.TryGetValue(managerId, out var manager))
            return manager;
        return null;
    }
}
