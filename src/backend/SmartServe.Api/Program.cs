using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.EntityFrameworkCore;
using Microsoft.Identity.Web;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;
using SmartServe.Api.Services;
using SmartServe.Api.Services.Directory;
using SmartServe.Api.Services.Email;
using SmartServe.Api.Testing;

var builder = WebApplication.CreateBuilder(args);

// ── Secrets: pull from Azure Key Vault when configured (Managed Identity). ──
var keyVaultUri = builder.Configuration["KeyVault:Uri"];
if (!string.IsNullOrWhiteSpace(keyVaultUri))
{
    builder.Configuration.AddAzureKeyVault(
        new Uri(keyVaultUri),
        new Azure.Identity.DefaultAzureCredential());
}

builder.Services.AddApplicationInsightsTelemetry();

// AuthN: Entra ID JWT bearer in real environments; TestAuthHandler only in Testing (no live issuer needed).
if (builder.Environment.EnvironmentName == "Testing")
{
    builder.Services.AddAuthentication(TestAuthHandler.SchemeName)
        .AddScheme<Microsoft.AspNetCore.Authentication.AuthenticationSchemeOptions, TestAuthHandler>(
            TestAuthHandler.SchemeName, _ => { });
}
else
{
    builder.Services
        .AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
        .AddMicrosoftIdentityWebApi(builder.Configuration.GetSection("AzureAd"));
}

// AuthZ: policies enforced server-side; approve/fulfil/retry-routing/admin role mappings are (proposed).
builder.Services.AddAuthorization(options =>
{
    options.FallbackPolicy = new AuthorizationPolicyBuilder()
        .RequireAuthenticatedUser()
        .Build();

    options.AddPolicy("CanCreateRequest", p => p.RequireRole(
        Roles.Employee, Roles.Manager, Roles.ItAdmin, Roles.AppAdmin)); // Employee confirmed; Manager/ItAdmin/AppAdmin submission is (proposed)
    // Confirmed: Employee policy, always filtered to the caller's own requests — no other role is granted access here.
    options.AddPolicy("CanViewOwnRequests", p => p.RequireRole(Roles.Employee));
    options.AddPolicy("CanApprove", p => p.RequireRole(Roles.Manager)); // (proposed) mapping
    options.AddPolicy("CanFulfil", p => p.RequireRole(Roles.ItAdmin)); // (proposed) mapping
    options.AddPolicy("CanRetryRouting", p => p.RequireRole(Roles.ItAdmin)); // (proposed) mapping
    options.AddPolicy("CanAudit", p => p.RequireRole(Roles.Auditor, Roles.AppAdmin)); // Auditor confirmed read-all; AppAdmin read-all is (proposed)
    options.AddPolicy("CanSecurityReview", p => p.RequireRole(Roles.SecurityReviewer));
    options.AddPolicy("CanAdminister", p => p.RequireRole(Roles.AppAdmin)); // (proposed) mapping
    options.AddPolicy("CanReadRequestTypes", p => p.RequireAuthenticatedUser()); // (proposed)
});

// DbContextFactory enables short-lived contexts around each SaveChanges/independent read for ordering tests.
var connString = builder.Configuration.GetConnectionString("SmartServeDb");
var isDevOrTesting = builder.Environment.IsDevelopment() || builder.Environment.EnvironmentName == "Testing";
if (string.IsNullOrWhiteSpace(connString) && !isDevOrTesting)
{
    // Confirmed persistence target is Azure SQL via EF Core (NFR-004); never fall back to in-memory outside Dev/Testing.
    throw new InvalidOperationException(
        "ConnectionStrings:SmartServeDb is required outside Development/Testing; in-memory persistence is not permitted.");
}
var inMemoryDbName = builder.Configuration["InMemoryDbName"] ?? $"smartserve-{Guid.NewGuid()}";
builder.Services.AddDbContextFactory<SmartServeDbContext>(opt =>
{
    if (string.IsNullOrWhiteSpace(connString))
        opt.UseInMemoryDatabase(inMemoryDbName);
    else
        opt.UseSqlServer(connString);
});

// UnconfiguredEmailSender runs only in Development/Testing; every other environment (incl. Staging) uses Graph.
if (isDevOrTesting)
{
    builder.Services.AddSingleton<IDirectoryService, InMemoryDirectoryService>();
    builder.Services.AddSingleton<IEmailSender, UnconfiguredEmailSender>();
}
else
{
    builder.Services.AddHttpClient<IDirectoryService, GraphDirectoryService>();
    builder.Services.AddHttpClient<IEmailSender, GraphEmailSender>();
}

builder.Services.AddScoped<NotificationService>();
builder.Services.AddScoped<WorkflowService>();
builder.Services.AddSingleton<NotificationReconciliationService>();
builder.Services.AddHostedService(sp => sp.GetRequiredService<NotificationReconciliationService>());

builder.Services.AddControllers()
    .AddJsonOptions(o => o.JsonSerializerOptions.Converters.Add(new JsonStringEnumConverter()));
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var allowedOrigins = builder.Configuration.GetSection("Cors:AllowedOrigins").Get<string[]>()
                     ?? new[] { "http://localhost:5173" };
builder.Services.AddCors(o => o.AddPolicy("spa", p =>
    p.WithOrigins(allowedOrigins).AllowAnyHeader().AllowAnyMethod()));

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var dbFactory = scope.ServiceProvider.GetRequiredService<IDbContextFactory<SmartServeDbContext>>();
    await using var db = await dbFactory.CreateDbContextAsync();
    if (db.Database.IsRelational())
        await db.Database.MigrateAsync();
    else
        await db.Database.EnsureCreatedAsync();
    await DbSeeder.SeedRequestTypesAsync(db);

    // Reconcile any Pending notifications left over from a previous process at startup.
    var reconciler = scope.ServiceProvider.GetRequiredService<NotificationReconciliationService>();
    await reconciler.ReconcileAsync();
}

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();

app.Use(async (ctx, next) =>
{
    ctx.Response.Headers["X-Content-Type-Options"] = "nosniff";
    ctx.Response.Headers["X-Frame-Options"] = "DENY";
    ctx.Response.Headers["Referrer-Policy"] = "no-referrer";
    await next();
});

app.UseCors("spa");
app.UseAuthentication();

// An Auditor principal may never mutate state, even if the same token also carries another role.
app.Use(async (ctx, next) =>
{
    var isMutating = HttpMethods.IsPost(ctx.Request.Method) || HttpMethods.IsPut(ctx.Request.Method)
        || HttpMethods.IsPatch(ctx.Request.Method) || HttpMethods.IsDelete(ctx.Request.Method);
    if (isMutating && ctx.User.Identity?.IsAuthenticated == true && ctx.User.IsInRole(Roles.Auditor))
    {
        ctx.Response.StatusCode = StatusCodes.Status403Forbidden;
        return;
    }
    await next();
});

app.UseAuthorization();

app.MapControllers();

// No anonymous endpoints anywhere — the health check also requires a valid bearer token.
app.MapGet("/health", async (IDbContextFactory<SmartServeDbContext> dbFactory, CancellationToken ct) =>
{
    try
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.Database.CanConnectAsync(ct) ? Results.Ok(new { status = "Healthy" }) : Results.StatusCode(503);
    }
    catch
    {
        return Results.StatusCode(503);
    }
}).RequireAuthorization();

app.Run();

// Exposed for integration testing via WebApplicationFactory.
public partial class Program { }
