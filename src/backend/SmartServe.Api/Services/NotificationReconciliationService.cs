using Microsoft.EntityFrameworkCore;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;

namespace SmartServe.Api.Services;

/// <summary>Marks notifications stuck Pending past their lease window as Failed; never touches active in-flight sends.</summary>
public class NotificationReconciliationService : BackgroundService
{
    private readonly IDbContextFactory<SmartServeDbContext> _dbFactory;
    private readonly ILogger<NotificationReconciliationService> _log;
    private readonly TimeSpan _interval = TimeSpan.FromMinutes(5);

    public NotificationReconciliationService(IDbContextFactory<SmartServeDbContext> dbFactory,
        ILogger<NotificationReconciliationService> log)
    {
        _dbFactory = dbFactory;
        _log = log;
    }

    /// <summary>Test seam only: invoked after a record is marked Failed but before SaveChangesAsync, to force a genuine concurrency race.</summary>
    public Func<NotificationRecord, Task>? OnBeforeSave { get; set; }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var reconciled = await ReconcileAsync(stoppingToken);
                if (reconciled > 0)
                    _log.LogWarning("Reconciled {Count} stale Pending notifications to Failed.", reconciled);
            }
            catch (Exception ex) when (!stoppingToken.IsCancellationRequested)
            {
                _log.LogError(ex, "Notification reconciliation sweep failed.");
            }

            try { await Task.Delay(_interval, stoppingToken); } catch (OperationCanceledException) { }
        }
    }

    /// <summary>Can be invoked on demand (startup or manually) in addition to the background loop.</summary>
    public async Task<int> ReconcileAsync(CancellationToken ct = default)
    {
        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var now = DateTimeOffset.UtcNow;
        var stale = await db.NotificationRecords
            .Where(n => n.Status == NotificationStatus.Pending && n.LeaseExpiresAt < now)
            .ToListAsync(ct);

        var reconciledCount = 0;
        foreach (var n in stale)
        {
            n.Status = NotificationStatus.Failed;
            n.Reason = "LeaseExpired";
            n.CompletedAt = now;
            n.RowVersion = Guid.NewGuid();
            try
            {
                if (OnBeforeSave is not null) await OnBeforeSave(n);
                // A concurrency conflict means an active send already finalized this record; keep its real outcome.
                await db.SaveChangesAsync(ct);
                reconciledCount++;
            }
            catch (DbUpdateConcurrencyException)
            {
                db.Entry(n).State = EntityState.Unchanged;
            }
        }

        return reconciledCount;
    }
}
