namespace SmartServe.Api.Services.Directory;

public record DirectoryUser(string Id, string DisplayName, string? Email);

/// <summary>Thrown for real directory/network/auth failures — distinct from a normal "not found".</summary>
public class DirectoryUnavailableException : Exception
{
    public DirectoryUnavailableException(string message, Exception? inner = null) : base(message, inner) { }
}

/// <summary>Abstraction over the directory/graph lookup used to resolve requester and manager identities.</summary>
public interface IDirectoryService
{
    /// <summary>Returns null when the user is simply not found; throws on a genuine directory failure.</summary>
    Task<DirectoryUser?> GetUserAsync(string userId, CancellationToken ct = default);

    /// <summary>Returns null when the user has no resolvable manager; throws on a genuine directory failure.</summary>
    Task<DirectoryUser?> GetManagerAsync(string userId, CancellationToken ct = default);
}
