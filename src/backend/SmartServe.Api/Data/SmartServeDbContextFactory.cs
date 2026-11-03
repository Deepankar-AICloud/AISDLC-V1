using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;

namespace SmartServe.Api.Data;

/// <summary>Design-time factory so `dotnet ef migrations add` can target SQL Server without running the app.</summary>
public class SmartServeDbContextFactory : IDesignTimeDbContextFactory<SmartServeDbContext>
{
    public SmartServeDbContext CreateDbContext(string[] args)
    {
        var builder = new DbContextOptionsBuilder<SmartServeDbContext>();
        builder.UseSqlServer("Server=tcp:localhost,1433;Database=SmartServeDb;Trusted_Connection=False;");
        return new SmartServeDbContext(builder.Options);
    }
}
