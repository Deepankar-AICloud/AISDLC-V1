using System.Text.RegularExpressions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using SmartServe.Api.Data;
using SmartServe.Api.Domain;
using SmartServe.Api.Services.Directory;
using SmartServe.Api.Services.Email;

namespace SmartServe.Api.Services;

/// <summary>Lease policy shared between NotificationService (writer) and the reconciliation sweep (reader).</summary>
public static class NotificationLeasePolicy
{
    // (proposed) lease timeout — long enough for a real send attempt, short enough to reconcile promptly.
    public const int LeaseMinutes = 15;
}

/// <summary>One shared create+finalize persistence path (CreatePendingAsync/FinalizeAsync) used by SendAsync and the direct terminal-outcome helpers.</summary>
public class NotificationService
{
    private static readonly Regex EmailPattern = new(@"^[^@\s]+@[^@\s]+\.[^@\s]+$", RegexOptions.Compiled);

    private readonly IDbContextFactory<SmartServeDbContext> _dbFactory;
    private readonly IDirectoryService _directory;
    private readonly IEmailSender _emailSender;
    private readonly ILogger<NotificationService> _log;

    public NotificationService(IDbContextFactory<SmartServeDbContext> dbFactory, IDirectoryService directory,
        IEmailSender emailSender, ILogger<NotificationService> log)
    {
        _dbFactory = dbFactory;
        _directory = directory;
        _emailSender = emailSender;
        _log = log;
    }

    private static bool IsValidEmail(string? email) => !string.IsNullOrWhiteSpace(email) && EmailPattern.IsMatch(email);

    /// <summary>Resolves the recipient, attempts delivery, and always finalizes to Accepted/NotSent/Failed — never left Pending.</summary>
    public async Task<NotificationRecord> SendAsync(Guid requestId, string recipientRole, NotificationTemplate template,
        string actorId, CancellationToken ct = default)
    {
        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var record = NewPendingRecord(requestId, recipientRole, template);

        try
        {
            // Pending record is created here, inside try, so any failure past this point (including cancellation) is always finalized below.
            await SaveNewRecordAsync(db, record, ct);

            var request = await db.PortalRequests.AsNoTracking().FirstAsync(r => r.Id == requestId, ct);
            var targetUserId = recipientRole == "Manager" ? request.ManagerId : request.RequesterId;

            if (string.IsNullOrWhiteSpace(targetUserId))
            {
                SetOutcome(record, NotificationStatus.NotSent, "RecipientUnresolved");
                return record;
            }

            DirectoryUser? user;
            try
            {
                user = await _directory.GetUserAsync(targetUserId, ct);
            }
            catch (DirectoryUnavailableException ex)
            {
                SetOutcome(record, NotificationStatus.Failed, $"DirectoryUnavailable:{ex.Message}");
                return record;
            }

            if (user is null)
            {
                SetOutcome(record, NotificationStatus.NotSent, "RecipientUnresolved");
                return record;
            }

            if (!IsValidEmail(user.Email))
            {
                SetOutcome(record, NotificationStatus.NotSent, "InvalidEmailAddress");
                return record;
            }

            record.RecipientAddress = user.Email;
            var (subject, body) = EmailTemplates.Build(template, request);
            var result = await _emailSender.SendAsync(new EmailMessage(user.Email!, subject, body), ct);

            var (status, reason) = result.Outcome switch
            {
                EmailSendOutcome.Accepted => (NotificationStatus.Accepted, result.Reason ?? "Accepted"),
                EmailSendOutcome.NotConfigured => (NotificationStatus.NotSent, result.Reason ?? "EmailNotConfigured"),
                _ => (NotificationStatus.Failed, result.Reason ?? "SendFailed")
            };
            SetOutcome(record, status, reason);
            return record;
        }
        catch (Exception ex)
        {
            // Covers cancellation and any unexpected error after the Pending record was created above.
            SetOutcome(record, NotificationStatus.Failed, ex.Message);
            return record;
        }
        finally
        {
            // Always finalize with a fresh, non-cancellable token — a cancelled request must not leave Pending.
            await FinalizeAsync(db, record);
        }
    }

    private static void SetOutcome(NotificationRecord record, NotificationStatus status, string reason)
    {
        record.Status = status;
        record.Reason = reason;
    }

    /// <summary>Records a NotSent outcome directly, when the caller already knows delivery can't be attempted.</summary>
    public Task<NotificationRecord> RecordNotSentAsync(Guid requestId, string recipientRole, NotificationTemplate template,
        string reason, CancellationToken ct = default)
        => RecordTerminalAsync(requestId, recipientRole, template, NotificationStatus.NotSent, reason, ct);

    /// <summary>Records a Failed outcome directly, for a known directory/network failure prior to any send attempt.</summary>
    public Task<NotificationRecord> RecordFailedAsync(Guid requestId, string recipientRole, NotificationTemplate template,
        string reason, CancellationToken ct = default)
        => RecordTerminalAsync(requestId, recipientRole, template, NotificationStatus.Failed, reason, ct);

    /// <summary>Shares SendAsync's create-then-finalize path for a known outcome that requires no dispatch attempt.</summary>
    private async Task<NotificationRecord> RecordTerminalAsync(Guid requestId, string recipientRole, NotificationTemplate template,
        NotificationStatus status, string reason, CancellationToken ct)
    {
        await using var db = await _dbFactory.CreateDbContextAsync(ct);
        var record = NewPendingRecord(requestId, recipientRole, template);
        try
        {
            await SaveNewRecordAsync(db, record, ct);
            SetOutcome(record, status, reason);
            return record;
        }
        catch (Exception ex)
        {
            SetOutcome(record, NotificationStatus.Failed, ex.Message);
            return record;
        }
        finally
        {
            await FinalizeAsync(db, record);
        }
    }

    private static NotificationRecord NewPendingRecord(Guid requestId, string recipientRole, NotificationTemplate template) => new()
    {
        PortalRequestId = requestId,
        RecipientRole = recipientRole,
        Template = template,
        Status = NotificationStatus.Pending,
        LeaseExpiresAt = DateTimeOffset.UtcNow.AddMinutes(NotificationLeasePolicy.LeaseMinutes)
    };

    private static async Task SaveNewRecordAsync(SmartServeDbContext db, NotificationRecord record, CancellationToken ct)
    {
        db.NotificationRecords.Add(record);
        await db.SaveChangesAsync(ct);
    }

    /// <summary>Test seam only: invoked immediately before FinalizeAsync's SaveChangesAsync, letting tests simulate a persistence failure distinct from a concurrency conflict.</summary>
    public Func<NotificationRecord, Task>? OnBeforeFinalizeSave { get; set; }

    /// <summary>Single persistence path for every finalization. A concurrency loss means another writer already
    /// finalized this exact record with its own real outcome, so that outcome stands. Any other save failure means
    /// the computed outcome never persisted, so the record is downgraded to Failed rather than returning an
    /// in-memory outcome nothing in the data store backs — the caller must never be told Accepted/NotSent for a
    /// row that was never written (an unwritten initial insert gives reconciliation nothing to find).</summary>
    private async Task FinalizeAsync(SmartServeDbContext db, NotificationRecord record)
    {
        record.CompletedAt = DateTimeOffset.UtcNow;
        record.RowVersion = Guid.NewGuid();
        try
        {
            if (OnBeforeFinalizeSave is not null) await OnBeforeFinalizeSave(record);
            await db.SaveChangesAsync(CancellationToken.None);
        }
        catch (DbUpdateConcurrencyException ex)
        {
            _log.LogInformation(ex, "Notification {NotificationId} finalize lost a concurrency race; the concurrent writer's outcome stands.", record.Id);
        }
        catch (Exception ex)
        {
            record.Status = NotificationStatus.Failed;
            record.Reason = $"FinalizePersistFailed:{ex.Message}";
            _log.LogWarning(ex, "Failed to persist final outcome for notification {NotificationId}; reporting Failed instead of an unpersisted outcome.", record.Id);
        }
    }
}
