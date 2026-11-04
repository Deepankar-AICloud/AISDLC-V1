# Monitoring and Observability {#monitoring-observability}

![Figure 29 — Monitoring and observability: sources, sinks and gaps](diagrams/rendered/22-monitoring-observability.png)

| Signal | Mechanism | Status |
|---|---|---|
| Application logs | `ILogger` (`Logging:LogLevel` Information / Warning for ASP.NET Core); `LogInformation` on request creation | [IMPLEMENTED]{.badge .ok} |
| Requests, dependencies, exceptions | Application Insights SDK (`AddApplicationInsightsTelemetry`) → workspace-based App Insights → Log Analytics | [IMPLEMENTED]{.badge .ok} (API only) |
| Distributed tracing / correlation | App Insights operation IDs; SPA sends `x-correlation-id`, stored on `AuditEntry.CorrelationId` | [PARTIAL]{.badge .partial} — header not propagated to telemetry |
| Audit log | `AuditEntries` table (business actions) | [PARTIAL]{.badge .partial} |
| Health endpoint | `/health` with EF Core DbContext check; App Service `healthCheckPath` | [IMPLEMENTED]{.badge .ok} |
| Deployment monitoring | `curl /health` smoke checks; release evidence pack | [IMPLEMENTED]{.badge .ok} |
| Alerts, dashboards, availability tests | Not defined in Bicep or elsewhere | [NOT CONFIRMED]{.badge .nc} |
| Frontend telemetry | No App Insights JS SDK; web app has no connection string | [NOT CONFIRMED]{.badge .nc} |
| Platform diagnostic settings | App Service, SQL, Key Vault diagnostic settings not configured | [NOT CONFIRMED]{.badge .nc} |
| AI token usage and cost | `reports/<run>/usage.json`, `dashboard.json`; tokens `unavailable` with Copilot CLI | [PARTIAL]{.badge .partial} |
| Security events | gitleaks/CodeQL/ZAP results in GitHub; no SIEM integration found | [PARTIAL]{.badge .partial} |

Table: Table 23.1 — Observability signals

Recommended additions:

- Alert rules: 5xx rate, `/health` failures, SQL DTU, App Service CPU/memory, Key Vault access failures.
- An App Insights availability test against `/health`.
- Diagnostic settings for every resource into Log Analytics.
- Browser telemetry in the SPA.
- A workbook covering requests by status and decision lead time.

# Error Handling and Resilience {#error-handling-resilience}

![Figure 30 — Error and retry handling across the application, deployments and the Agentic SDLC](diagrams/rendered/28-error-retry-workflow.png)

| Concern | Current behaviour | Recommendation |
|---|---|---|
| API errors | Explicit 400/403/404; automatic 400 for invalid models; unhandled exceptions return 500 without ProblemDetails | `UseExceptionHandler` + `AddProblemDetails`; log with correlation ID |
| Database transience | EF Core SQL Server provider without `EnableRetryOnFailure` | Enable retry-on-failure; pair it with execution strategies for the two-step save (request + audit) |
| Consistency | Request change and audit row saved in **two** `SaveChangesAsync` calls; a failure between them leaves an unaudited change | Save both in one unit of work / transaction |
| Concurrency | No concurrency token; simultaneous decisions can race | Add a `rowversion` concurrency token and handle 409 |
| Idempotency | POSTs are not idempotent (duplicate submissions possible) | Idempotency key or duplicate detection (open question in TASK-23) |
| Client | SPA shows the error text; no retry or back-off | Retry idempotent GETs with back-off; friendly messages |
| Startup | `Migrate()` at startup; Key Vault provider failure stops the app | Run migrations in the pipeline; health-gate the slot before swap (already done) |
| Deployments | Smoke tests retry 5–6 times; production failure stops with `DEPLOYMENT_FAILED` | Optional automatic swap-back after a failed post-swap health check |
| Agentic SDLC | QC diagnosis, model escalation, `auto` fallback, JSON re-ask, patch persistence, fail-safe comments with retries | Keep; add per-stage timeouts in the job |

Table: Table 24.1 — Error handling and resilience

# Performance and Scalability {#performance-scalability}

No workload figures (users, requests per second, data volume) and no latency or availability targets exist in the workspace. NFR-23 records them as open questions. The table lists only confirmed facts and recommended approaches.

| Topic | Confirmed | Recommended |
|---|---|---|
| Application scaling | One App Service instance (B1 / P1v3); stateless API (bearer tokens), so horizontal scale-out is possible | Autoscale rules on CPU/requests once targets exist |
| Database scaling | Basic (dev/staging), S1 (production) DTU model | Size against measured load; consider serverless vCore |
| Caching | None | Cache reference data (request types) once implemented |
| Queues / asynchronous work | None | Use a queue (e.g. Service Bus) for e-mail notifications to decouple delivery |
| Connection pooling | ADO.NET pooling (default) | — |
| Rate limiting | None | ASP.NET Core rate limiter or Front Door/WAF |
| Timeouts / retry / circuit breaker | Framework defaults only | EF retry-on-failure; Polly for future outbound calls (Graph/e-mail) |
| Pagination | List endpoints return everything (requests) or 500 (audit) | Server-side paging and filtering |
| Load balancing | App Service built-in | — |
| Health checks | `/health` incl. DB | Separate liveness and readiness |
| Graceful degradation | Not designed | Queue notifications; read-only mode |

Table: Table 25.1 — Performance and scalability

# Backup and Disaster Recovery {#backup-dr}

| Item | Confirmed state | Gap / recommendation |
|---|---|---|
| Azure SQL backups | Platform automated backups (default retention); not configured in Bicep | Define the PITR retention and long-term retention policy; document restore tests |
| Geo-redundancy | Production SQL zone-redundant (S1) and ZRS storage within one region | Define RPO/RTO; consider geo-replication / failover groups |
| Key Vault | Soft delete enabled; purge protection not set | Enable purge protection for production |
| App Service | Code redeployable from Git; slot swap for rollback | Document the re-provisioning runbook (Bicep) |
| Configuration | Infrastructure as code; secrets in Key Vault | Back up Entra app registrations and role assignments (manual today) |
| Audit data | In the same database | Archive or export to immutable storage if required by compliance |
| RPO / RTO | **Not defined** | Obtain from the business (§34) |

Table: Table 26.1 — Backup and disaster recovery
