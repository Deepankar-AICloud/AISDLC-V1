---
name: azure-resource-analyzer
description: 'Comprehensive Azure resource group analyzer that generates detailed infrastructure reports using Azure CLI. Use when asked to "analyze resource group", "audit Azure resources", "generate infrastructure report", "review Azure deployment", "list all resources in resource group", "resource inventory", or "Azure resource assessment". Automatically handles all prompts and confirmations without user intervention.'
---

# Azure Resource Group Analyzer

A skill for performing comprehensive analysis of Azure resource groups and generating detailed infrastructure reports. This skill uses Azure CLI commands to gather information about all deployed resources and produces a markdown report with findings, security assessments, and recommendations.

## When to Use This Skill

- User asks to "analyze a resource group" or "audit Azure resources"
- User wants a "resource inventory" or "infrastructure report"
- User needs to "review Azure deployment" or "assess Azure infrastructure"
- User asks "what's deployed in my resource group"
- User wants to understand their Azure resource landscape
- User needs security and cost assessment of Azure resources

## Prerequisites

- Azure CLI installed and available in PATH
- User must be logged in to Azure (`az login` completed)
- Appropriate permissions to read resources in the target resource group
- The resource group must exist in the subscription

## Step-by-Step Workflow

### Step 1: Identify the Target Resource Group

Get the resource group name from the user or context. If analyzing a specific resource group mentioned in code or configuration files (like `setup-azure.sh`), extract the name from there.

```bash
# Verify the resource group exists
az group show --name <RESOURCE_GROUP_NAME> --output json
```

### Step 2: List All Resources in the Resource Group

Retrieve the complete inventory of resources:

```bash
az resource list --resource-group <RESOURCE_GROUP_NAME> --output json
```

This provides an overview including:
- Resource names and types
- Locations
- SKUs
- Provisioning states
- Tags
- Creation/modification timestamps

### Step 3: Gather Detailed Information for Each Resource Type

For each resource type found, run the appropriate detail command. **IMPORTANT**: Always use `--output json` and append `2>/dev/null` or handle errors gracefully. When prompted for confirmations, auto-accept with `--yes` or `-y` flags where applicable.

#### Container Apps
```bash
az containerapp show --name <NAME> --resource-group <RG> --output json
az containerapp env show --name <ENV_NAME> --resource-group <RG> --output json
```

#### Container Registry
```bash
az acr show --name <NAME> --resource-group <RG> --output json
az acr repository list --name <NAME> --output json 2>/dev/null
```

#### Cosmos DB
```bash
az cosmosdb show --name <NAME> --resource-group <RG> --output json
```

#### PostgreSQL Flexible Server
```bash
az postgres flexible-server show --name <NAME> --resource-group <RG> --output json
```

#### Azure AI Services / Cognitive Services
```bash
az cognitiveservices account show --name <NAME> --resource-group <RG> --output json
```

#### Azure Load Testing
```bash
az load show --name <NAME> --resource-group <RG> --output json
```

#### Azure Managed Grafana
```bash
# Auto-install extension if prompted
az config set extension.dynamic_install_allow_preview=true 2>/dev/null
az config set extension.use_dynamic_install=yes_without_prompt 2>/dev/null
az grafana show --name <NAME> --resource-group <RG> --output json
```

#### Log Analytics Workspaces
```bash
az monitor log-analytics workspace list --resource-group <RG> --output json
```

#### Managed Identities
These are captured in the initial resource list - no additional command needed.

#### App Insights
```bash
az monitor app-insights component show --app <NAME> --resource-group <RG> --output json 2>/dev/null
# OR use REST API if extension not available
az rest --method get --uri "/subscriptions/<SUB_ID>/resourceGroups/<RG>/providers/Microsoft.Insights/components/<NAME>?api-version=2020-02-02" --output json 2>/dev/null
```

### Step 4: Generate the Analysis Report

Create a comprehensive markdown report with these sections:

#### Report Structure

```markdown
# Azure Resource Analysis Report

**Resource Group:** `<name>`
**Location:** <location>
**Report Generated:** <date>
**Subscription ID:** `<subscription_id>`

---

## Executive Summary
[High-level overview with key findings table showing resource health status]

## Resource Inventory
[Organized by resource category with detailed tables]

### 1. Compute & Container Resources
### 2. Container Registry
### 3. Database Resources
### 4. Monitoring & Observability
### 5. AI Services
### 6. Load Testing
### 7. Managed Identities

## Architecture Diagram (Text)
[ASCII diagram showing resource relationships]

## Security Assessment
### ✅ Strengths
### ⚠️ Areas for Improvement
### 🔐 Recommendations

## Issues & Recommendations
### 🔴 Critical Issues
### 🟡 Warnings
### 🟢 Optimization Opportunities

## Cost Considerations
[Estimated monthly costs and optimization tips]

## Resource Timeline
[Creation dates of resources]

## Summary
[Key takeaways and immediate actions required]
```

### Step 5: Return the Report in Chat

**IMPORTANT**: Do NOT create a markdown file. Instead, return the complete analysis report directly in the chat response. The user can copy/save it themselves if needed.

## Key Information to Extract Per Resource Type

### Container Apps
- FQDN and ingress configuration
- Current revision and image
- CPU/Memory allocation
- Min/Max replicas
- Environment variables (names only, not values)
- Running status

### Databases (Cosmos DB, PostgreSQL)
- Provisioning state (CRITICAL - flag if Failed)
- Server state (Running/Stopped)
- SKU/Tier
- Storage configuration
- Backup policies
- Network access settings
- Authentication methods

### Container Registry
- Login server
- SKU tier
- Admin enabled status
- Repository list
- Retention policies

### AI Services
- Endpoint URLs
- SKU
- Available APIs/Capabilities
- Authentication mode

### Monitoring Resources
- Workspace IDs
- Retention periods
- Pricing tiers

## Auto-Accept Configurations

Before running commands, set these to avoid interactive prompts:

```bash
# Disable extension install prompts
az config set extension.use_dynamic_install=yes_without_prompt 2>/dev/null
az config set extension.dynamic_install_allow_preview=true 2>/dev/null

# Set default output format
az config set core.output=json 2>/dev/null
```

## Error Handling

- If a command fails, log the error and continue with other resources
- Use `2>/dev/null` to suppress error output for optional queries
- Check exit codes and provide fallback messages
- Never let a single resource failure stop the entire analysis

## Status Indicators

Use these emoji indicators in the report:
- ✅ Healthy/Succeeded
- ⚠️ Warning/Attention needed
- ⛔ Stopped/Disabled
- 🔴 Critical/Failed

## Security Flags to Check

1. **Public Network Access** - Flag if enabled on sensitive resources
2. **Local Authentication** - Note if disabled (good) or enabled
3. **Encryption** - Platform vs Customer managed keys
4. **Private Endpoints** - Presence or absence
5. **Zone Redundancy** - Enabled or disabled
6. **Managed Identities** - System vs User assigned

## Cost Estimation Guidelines

Provide rough estimates based on:
- Container Apps: Consumption-based (~$0-50/month for light usage)
- ACR Basic: ~$5/month
- PostgreSQL B1ms: ~$25/month (when running)
- Cosmos Serverless: Pay per RU consumed
- Grafana Standard: ~$60-90/month
- Log Analytics: ~$2.30/GB ingested

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "az: command not found" | Azure CLI not installed - inform user |
| "Please run 'az login'" | User not authenticated - inform user |
| "Resource not found" | Resource may have been deleted - skip and note |
| Extension prompts | Pre-configure auto-install settings |
| Permission denied | Note in report, continue with accessible resources |

## Example Output

The report should be returned directly in the chat response as formatted markdown. Do NOT save to a file unless explicitly requested by the user.

## References

- [Azure CLI Documentation](https://docs.microsoft.com/en-us/cli/azure/)
- [Azure Resource Types](https://docs.microsoft.com/en-us/azure/azure-resource-manager/management/resource-providers-and-types)
- [Azure Pricing Calculator](https://azure.microsoft.com/en-us/pricing/calculator/)
