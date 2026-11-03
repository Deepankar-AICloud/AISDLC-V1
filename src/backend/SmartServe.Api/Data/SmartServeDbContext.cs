using Microsoft.EntityFrameworkCore;
using SmartServe.Api.Domain;

namespace SmartServe.Api.Data;

public class SmartServeDbContext : DbContext
{
    public SmartServeDbContext(DbContextOptions<SmartServeDbContext> options) : base(options) { }

    public DbSet<PortalRequest> PortalRequests => Set<PortalRequest>();
    public DbSet<RequestType> RequestTypes => Set<RequestType>();
    public DbSet<RequestAudit> RequestAudits => Set<RequestAudit>();
    public DbSet<NotificationRecord> NotificationRecords => Set<NotificationRecord>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<PortalRequest>(e =>
        {
            e.HasKey(x => x.Id);
            e.Property(x => x.Status).HasConversion<string>();
            e.Property(x => x.Kind).HasConversion<string>();
            e.HasOne(x => x.RequestType).WithMany().HasForeignKey(x => x.RequestTypeId).OnDelete(DeleteBehavior.Restrict);
            e.HasIndex(x => x.RequesterId);
            e.HasIndex(x => x.ManagerId);
            e.HasIndex(x => x.Status);
            e.HasIndex(x => x.Kind);
            e.Property(x => x.RowVersion).IsConcurrencyToken();
        });

        b.Entity<RequestType>(e =>
        {
            e.HasKey(x => x.Id);
            e.Property(x => x.Kind).HasConversion<string>();
            e.HasIndex(x => new { x.Kind, x.IsActive });
        });

        b.Entity<RequestAudit>(e =>
        {
            e.HasKey(x => x.Id);
            e.Property(x => x.OldStatus).HasConversion<string>();
            e.Property(x => x.NewStatus).HasConversion<string>();
            e.HasIndex(x => x.PortalRequestId);
            e.HasIndex(x => x.Timestamp);
        });

        b.Entity<NotificationRecord>(e =>
        {
            e.HasKey(x => x.Id);
            e.Property(x => x.Template).HasConversion<string>();
            e.Property(x => x.Status).HasConversion<string>();
            e.Property(x => x.RowVersion).IsConcurrencyToken();
            e.HasIndex(x => x.PortalRequestId);
            e.HasIndex(x => new { x.Status, x.LeaseExpiresAt });
        });
    }
}
