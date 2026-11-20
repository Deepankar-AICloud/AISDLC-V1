namespace SmartServe.Api.Services;

/// <summary>Business-day arithmetic used only for provisional NFR-003 reporting (TASK-012); see docs/decisions/access-request-contract.md for the pending confirmed definition.</summary>
public static class BusinessDayCalculator
{
    /// <summary>Adds <paramref name="businessDays"/> calendar days to <paramref name="start"/>, skipping Saturdays and Sundays. No holiday calendar (not yet defined).</summary>
    public static DateTimeOffset AddBusinessDays(DateTimeOffset start, int businessDays)
    {
        var result = start;
        var remaining = businessDays;
        while (remaining > 0)
        {
            result = result.AddDays(1);
            if (result.DayOfWeek is not (DayOfWeek.Saturday or DayOfWeek.Sunday))
                remaining--;
        }
        return result;
    }
}
