using Microsoft.EntityFrameworkCore;
using SmartServe.Api.Domain;

namespace SmartServe.Api.Data;

public class SmartServeDbContext : DbContext
{
    public SmartServeDbContext(DbContextOptions<SmartServeDbContext> options) : base(options) { }

    public DbSet<AccessRequest> AccessRequests => Set<AccessRequest>();
    public DbSet<RequestComment> Comments => Set<RequestComment>();
    public DbSet<ApprovalStep> Approvals => Set<ApprovalStep>();
    public DbSet<AuditEntry> AuditEntries => Set<AuditEntry>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<AccessRequest>(e =>
        {
            e.HasKey(x => x.Id);
            e.HasMany(x => x.Comments).WithOne().HasForeignKey(c => c.AccessRequestId).OnDelete(DeleteBehavior.Cascade);
            e.HasMany(x => x.Approvals).WithOne().HasForeignKey(a => a.AccessRequestId).OnDelete(DeleteBehavior.Cascade);
            e.Property(x => x.Status).HasConversion<string>();
            e.Property(x => x.Category).HasConversion<string>();
            e.HasIndex(x => x.RequesterId);
            e.HasIndex(x => x.Status);
        });

        b.Entity<AuditEntry>(e =>
        {
            e.HasKey(x => x.Id);
            e.HasIndex(x => x.AccessRequestId);
            e.HasIndex(x => x.Timestamp);
        });
    }
}
