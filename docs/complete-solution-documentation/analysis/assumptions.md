# Assumptions

These assumptions were needed to interpret the workspace. Each one is labelled in the main document and must be confirmed by the project team.

| # | Assumption | Basis | Impact if wrong |
|---|---|---|---|
| A1 | The six role names are issued by Entra ID as **app roles** in the `roles` claim | `User.IsInRole(...)` and `RequireRole(...)` with string constants; no app-registration manifest in the workspace | Authorization would fail for every user |
| A2 | Azure SQL encryption at rest (TDE) and Storage Service Encryption use platform defaults | Not set in Bicep; platform defaults apply | Compliance statements may need adjusting |
| A3 | Azure SQL automated backups use default retention | No backup configuration in Bicep | RPO/RTO statements may need adjusting |
| A4 | Kestrel listens on `http://localhost:5000` locally | No `launchSettings.json`; .NET 8 default; the Vite proxy targets 5000 | Local proxy settings would need adjusting |
| A5 | Enum JSON values are numbers on the wire | No `JsonStringEnumConverter` registered; System.Text.Json default | The contract finding (R-03) would not apply |
| A6 | The staging-slot Key Vault access fails without a role assignment | The slot has its own system-assigned identity, no role assignment, and `KeyVault__Uri` set | R-06 severity would be lower |
| A7 | CodeQL runs via GitHub **default setup** | No CodeQL workflow file; README and the gate workflow query the "CodeQL" workflow runs | The SAST description would change |
| A8 | Staging and production may be separate App Service apps | Separate secrets (`AZURE_API_APP_STAGING`, `AZURE_API_APP_PROD`) | Environment-isolation statements would change |
| A9 | The SmartServe runtime makes no AI/LLM calls | No AI SDK references in `src/` | The AI architecture chapter would need a runtime section |
| A10 | Personal data consists of Entra object IDs and free text | Entity fields; `oid` claim used as `UserId` | The privacy classification would change |
