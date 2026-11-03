using Microsoft.EntityFrameworkCore;
using SmartServe.Api.Domain;

namespace SmartServe.Api.Data;

public static class DbSeeder
{
    public static async Task SeedRequestTypesAsync(SmartServeDbContext db, CancellationToken ct = default)
    {
        if (await db.RequestTypes.AnyAsync(ct)) return;

        // (proposed) initial catalog: specific request-type names/descriptions aren't specified by BRD/PRD/ARCH-23.
        db.RequestTypes.AddRange(
            new RequestType { Kind = RequestKind.Access, Name = "Application Access", Description = "Access to a business application." },
            new RequestType { Kind = RequestKind.Access, Name = "VPN Access", Description = "Remote network access." },
            new RequestType { Kind = RequestKind.Service, Name = "Laptop Request", Description = "New or replacement laptop." },
            new RequestType { Kind = RequestKind.Service, Name = "Password Support", Description = "Password reset / unlock." });

        await db.SaveChangesAsync(ct);
    }
}
