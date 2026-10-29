using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.EntityFrameworkCore;
using Microsoft.Identity.Web;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;
using SmartServe.Api.Services;

var builder = WebApplication.CreateBuilder(args);

// ── Secrets: pull from Azure Key Vault when configured (Managed Identity). ──
var keyVaultUri = builder.Configuration["KeyVault:Uri"];
if (!string.IsNullOrWhiteSpace(keyVaultUri))
{
    builder.Configuration.AddAzureKeyVault(
        new Uri(keyVaultUri),
        new Azure.Identity.DefaultAzureCredential());
}

// ── Telemetry ──
builder.Services.AddApplicationInsightsTelemetry();

// ── AuthN: Microsoft Entra ID (JWT bearer). ──
builder.Services
    .AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddMicrosoftIdentityWebApi(builder.Configuration.GetSection("AzureAd"));

// ── AuthZ: policies enforced server-side (never UI-only). ──
builder.Services.AddAuthorization(options =>
{
    options.AddPolicy("CanCreateRequest", p => p.RequireRole(
        Roles.Employee, Roles.Manager, Roles.ItAdmin, Roles.AppAdmin, Roles.SecurityReviewer));
    options.AddPolicy("CanApprove", p => p.RequireRole(
        Roles.Manager, Roles.SecurityReviewer, Roles.ItAdmin));
    options.AddPolicy("CanAudit", p => p.RequireRole(Roles.Auditor, Roles.AppAdmin));
    options.AddPolicy("CanAdminister", p => p.RequireRole(Roles.AppAdmin));
});

// ── Data access. In-memory for local/dev when no connection string is set. ──
var connString = builder.Configuration.GetConnectionString("SmartServeDb");
builder.Services.AddDbContext<SmartServeDbContext>(opt =>
{
    if (string.IsNullOrWhiteSpace(connString))
        opt.UseInMemoryDatabase("smartserve-dev");
    else
        opt.UseSqlServer(connString);
});

builder.Services.AddScoped<WorkflowService>();
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddHealthChecks().AddDbContextCheck<SmartServeDbContext>();

// CORS for the SPA frontend (origins come from configuration).
var allowedOrigins = builder.Configuration.GetSection("Cors:AllowedOrigins").Get<string[]>()
                     ?? new[] { "http://localhost:5173" };
builder.Services.AddCors(o => o.AddPolicy("spa", p =>
    p.WithOrigins(allowedOrigins).AllowAnyHeader().AllowAnyMethod()));

var app = builder.Build();

// Apply migrations / ensure created for relational providers.
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<SmartServeDbContext>();
    if (db.Database.IsRelational())
        db.Database.Migrate();
    else
        db.Database.EnsureCreated();
}

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();

// Security headers.
app.Use(async (ctx, next) =>
{
    ctx.Response.Headers["X-Content-Type-Options"] = "nosniff";
    ctx.Response.Headers["X-Frame-Options"] = "DENY";
    ctx.Response.Headers["Referrer-Policy"] = "no-referrer";
    await next();
});

app.UseCors("spa");
app.UseAuthentication();
app.UseAuthorization();

app.MapControllers();
app.MapHealthChecks("/health").AllowAnonymous();

app.Run();

// Exposed for integration testing via WebApplicationFactory.
public partial class Program { }
