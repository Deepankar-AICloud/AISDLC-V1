# Assumptions

These assumptions were needed to interpret the workspace. Each one is labelled in the main document and must be confirmed by the project team.

| # | Assumption | Basis | Impact if wrong |
|---|---|---|---|
| A1 | The six role names are issued by Entra ID as **app roles** in the `roles` claim | `RequireRole(...)` with string constants; confirmed for DEV, where `setup-dev.ps1` defines the roles on the API app registration | Authorization would fail for every user |
| A2 | Azure SQL encryption at rest (TDE) and Storage Service Encryption use platform defaults | Not set in Bicep; platform defaults apply | Compliance statements may need adjusting |
| A3 | Azure SQL automated backups use default retention | No backup configuration in Bicep | RPO/RTO statements may need adjusting |
| A4 | Kestrel listens on `http://localhost:5000` locally | No `launchSettings.json`; .NET 8 default; the Vite proxy targets 5000 | Local proxy settings would need adjusting |
| A5 | The subscription policy that disables public network access on SQL, Key Vault and Storage applies to every SmartServe environment | Observed in the DEV subscription during deployment | Private networking could be optional elsewhere |
| A6 | Manager routing and e-mail will work once the API identity holds Graph application permissions for directory read and `Mail.Send` and a sender mailbox is set | Code uses `/users/{id}`, `/users/{id}/manager` and `/users/{sender}/sendMail` with the managed identity | Additional permissions or a different sender model may be needed |
| A7 | CodeQL runs via GitHub **default setup** | No CodeQL workflow file; the gate workflow queries the "CodeQL" workflow runs | The SAST description would change |
| A8 | Staging is a slot of the production API app | `deploy-production.yml` swaps the `staging` slot into production | Environment-isolation statements would change |
| A9 | The SmartServe runtime makes no AI/LLM calls | No AI SDK references in `src/` | The AI architecture chapter would need a runtime section |
| A10 | Personal data consists of Entra object IDs, e-mail addresses and free text | Entity fields; `oid` claim used as `UserId`; `NotificationRecord.RecipientAddress` | The privacy classification would change |
