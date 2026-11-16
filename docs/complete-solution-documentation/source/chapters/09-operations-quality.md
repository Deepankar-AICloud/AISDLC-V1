# Monitoring and Observability {#monitoring-observability}

![Figure 29 — Monitoring and observability: sources, sinks and gaps](diagrams/rendered/22-monitoring-observability.png)

| Signal | Mechanism | Status |
|---|---|---|
| Application logs | `ILogger` (`Logging:LogLevel` Information / Warning for ASP.NET Core); notification concurrency events logged | [IMPLEMENTED]{.badge .ok} |
| Requests, dependencies, exceptions | Application Insights SDK (`AddApplicationInsightsTelemetry`) → workspace-based App Insights → Log Analytics | [IMPLEMENTED]{.badge .ok} (API only) |
| Distributed tracing / correlation | App Insights operation IDs; SPA sends `x-correlation-id`, which the API does not store or propagate | [PARTIAL]{.badge .partial} |
| Audit log | `RequestAudits` table (every status change, old/new status) | [IMPLEMENTED]{.badge .ok} |
| Notification outcomes | `NotificationRecords` (Accepted / NotSent / Failed with reason); stale *Pending* marked *Failed* every 5 minutes | [IMPLEMENTED]{.badge .ok} — no alert on failures |
| Health endpoint | `/health` checks database connectivity; requires a token; App Service `healthCheckPath` | [PARTIAL]{.badge .partial} — platform probe receives 401 |
| Deployment monitoring | DEV smoke test (API up, web reachable); release evidence pack for production | [IMPLEMENTED]{.badge .ok} |
| Alerts, dashboards, availability tests | Not defined in Bicep or elsewhere | [NOT CONFIRMED]{.badge .nc} |
| Frontend telemetry | No App Insights JS SDK; web app has no connection string | [NOT CONFIRMED]{.badge .nc} |
| Platform diagnostic settings | App Service, SQL, Key Vault diagnostic settings not configured | [NOT CONFIRMED]{.badge .nc} |
| AI token usage and cost | `reports/<run>/usage.json`, `dashboard.json`; tokens `unavailable` with Copilot CLI | [PARTIAL]{.badge .partial} |
| Security events | gitleaks/CodeQL/ZAP results in GitHub; no SIEM integration found | [PARTIAL]{.badge .partial} |

Table: Table 23.1 — Observability signals

Recommended additions:

- Alert rules: 5xx rate, SQL DTU, App Service CPU/memory, Key Vault access failures, and notification records with status *Failed*.
- An App Insights availability test against the web root (and an authenticated or separate liveness check for the API).
- Diagnostic settings for every resource into Log Analytics.
- Browser telemetry in the SPA.
- A workbook covering requests by status, decision lead time and notification outcomes.

# Error Handling and Resilience {#error-handling-resilience}

![Figure 30 — Error and retry handling across the application, deployments and the Agentic SDLC](diagrams/rendered/28-error-retry-workflow.png)

| Concern | Current behaviour | Recommendation |
|---|---|---|
| API errors | Explicit 400/404; automatic 400 for invalid models; 403 from policies; unhandled exceptions return 500 without ProblemDetails | `UseExceptionHandler` + `AddProblemDetails`; log with correlation ID |
| Database transience | EF Core SQL Server provider without `EnableRetryOnFailure` | Enable retry-on-failure with execution strategies |
| Consistency | Status change and audit row saved in **one** `SaveChanges`; tested on SQLite | Keep; add a SQL Server test |
| Concurrency | GUID concurrency tokens on requests and notification records; a losing transition returns 400 and rolls back with its audit row | Return 409 instead of 400 for concurrent changes |
| External services (Graph) | Directory outage keeps the request *Submitted* and records *Failed*; mail failures recorded per message; no automatic retry | IT-admin `retry-routing` exists for routing; consider automatic retry with back-off for e-mail |
| Idempotency | POSTs are not idempotent (duplicate submissions possible) | Idempotency key or duplicate detection |
| Client | SPA shows the error text; interactive sign-in on token expiry; no retry | Retry idempotent GETs with back-off; friendlier messages |
| Startup | `MigrateAsync` and seeding at startup; Key Vault provider failure stops the app | Run migrations in the pipeline for multi-instance scale-out |
| Deployments | DEV smoke test waits up to 10 minutes; production failure stops with `DEPLOYMENT_FAILED` | Optional automatic swap-back after a failed post-swap health check |
| Agentic SDLC | QC diagnosis, model escalation, `auto` fallback, JSON re-ask, patch persistence, fail-safe comments with retries, hand-off to CI/CD after code | Keep; add per-stage timeouts in the job |

Table: Table 24.1 — Error handling and resilience

# Performance and Scalability {#performance-scalability}

No workload figures (users, requests per second, data volume) and no latency or availability targets exist in the workspace. NFR-23 records them as open questions. The table lists only confirmed facts and recommended approaches.

| Topic | Confirmed | Recommended |
|---|---|---|
| Application scaling | One App Service instance (B1 in DEV; S1/P1v3 designed for staging/production); stateless API, so horizontal scale-out is possible | Autoscale rules on CPU/requests once targets exist; move migrations out of startup first |
| Database scaling | Basic (dev/staging), S1 (production) DTU model | Size against measured load; consider serverless vCore |
| Caching | None | Cache request types (read on every form load) |
| Queues / asynchronous work | None; e-mail is sent synchronously after the transaction commits, with a background reconciliation job | A queue (e.g. Service Bus) if e-mail latency affects request times |
| Connection pooling | ADO.NET pooling (default); short-lived contexts via `IDbContextFactory` | — |
| Rate limiting | None | ASP.NET Core rate limiter or Front Door/WAF |
| Timeouts / retry / circuit breaker | Framework defaults only | EF retry-on-failure; Polly for Graph calls |
| Pagination | Audit and security-review endpoints paged (default 50, max 200); own-request list unpaged | Page the own-request list if volumes grow |
| Load balancing | App Service built-in | — |
| Health checks | `/health` including DB, token required | Separate anonymous liveness and authenticated readiness, if NFR-001 allows |
| Graceful degradation | Directory outages leave requests *Submitted* for retry; e-mail failures do not block transitions | Read-only mode |

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
