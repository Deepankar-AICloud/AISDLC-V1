using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using SmartServe.Api.Services.Directory;
using SmartServe.Api.Services.Email;

namespace SmartServe.Tests.TestSupport;

/// <summary>WebApplicationFactory for the Testing environment with an isolated in-memory DB and swappable fake directory/email services.</summary>
public class SmartServeWebApplicationFactory : WebApplicationFactory<Program>
{
    public FakeDirectoryService Directory { get; } = new();
    public FakeEmailSender EmailSender { get; } = new();

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Testing");
        builder.ConfigureAppConfiguration((_, config) =>
        {
            config.AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["InMemoryDbName"] = $"smartserve-tests-{Guid.NewGuid()}"
            });
        });
        builder.ConfigureServices(services =>
        {
            services.RemoveAll<IDirectoryService>();
            services.AddSingleton<IDirectoryService>(Directory);
            services.RemoveAll<IEmailSender>();
            services.AddSingleton<IEmailSender>(EmailSender);
        });
    }

    /// <summary>Builds the "Bearer test:&lt;userId&gt;:&lt;role1,role2&gt;" header value for TestAuthHandler.</summary>
    public static string BearerFor(string userId, params string[] roles) => $"Bearer test:{userId}:{string.Join(',', roles)}";
}
