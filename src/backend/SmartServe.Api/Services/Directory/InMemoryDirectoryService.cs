using System.Collections.Concurrent;

namespace SmartServe.Api.Services.Directory;

/// <summary>Development/Testing directory stand-in (bounded, thread-safe in-memory map); never registered in Production.</summary>
public class InMemoryDirectoryService : IDirectoryService
{
    private readonly ConcurrentDictionary<string, DirectoryUser> _users = new();
    private readonly ConcurrentDictionary<string, string> _managerOf = new();

    public InMemoryDirectoryService()
    {
        _users["demo-employee"] = new DirectoryUser("demo-employee", "Demo Employee", "demo.employee@contoso.example");
        _users["demo-manager"] = new DirectoryUser("demo-manager", "Demo Manager", "demo.manager@contoso.example");
        _managerOf["demo-employee"] = "demo-manager";
    }

    public Task<DirectoryUser?> GetUserAsync(string userId, CancellationToken ct = default)
        => Task.FromResult(_users.TryGetValue(userId, out var u) ? u : null);

    public Task<DirectoryUser?> GetManagerAsync(string userId, CancellationToken ct = default)
    {
        if (_managerOf.TryGetValue(userId, out var managerId) && _users.TryGetValue(managerId, out var manager))
            return Task.FromResult<DirectoryUser?>(manager);
        return Task.FromResult<DirectoryUser?>(null);
    }
}
