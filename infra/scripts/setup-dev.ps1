#Requires -Version 7.3
<#
.SYNOPSIS
  One-time setup so the "Deploy — DEV" GitHub workflow can provision and deploy
  SmartServe DEV to Azure App Service on every merge to main.

.DESCRIPTION
  Idempotent; safe to re-run. Uses your current `az login` and `gh auth` sessions.
  Only things a pipeline cannot do for itself are done here; the pipeline runs
  infra/main.bicep and deploys the code.
    1. Registers the required resource providers.
    2. Creates a user-assigned managed identity for GitHub Actions (OIDC, no secrets)
       with Contributor + Role Based Access Control Administrator on the resource group.
    3. Creates the Entra ID app registrations: "SmartServe API (dev)" (scope + app roles)
       and "SmartServe Web (dev)" (SPA, redirect URI = the DEV web app), and assigns you
       the Employee role.
    4. Writes the GitHub `dev` environment secrets/variables.

  Requires Owner (or Contributor + User Access Administrator) on the resource group and
  permission to create app registrations in the tenant.
#>
param(
    [string]$ResourceGroup = 'rg-aisdlc-v1',
    [string]$Repo = 'Deepankar-AICloud/AISDLC-V1',
    [switch]$RunWorkflow
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$envName = 'dev'

function Invoke-Graph([string]$Method, [string]$Uri, $Body) {
    $file = New-TemporaryFile
    try {
        $Body | ConvertTo-Json -Depth 10 | Set-Content -Path $file -Encoding utf8
        az rest --method $Method --uri $Uri --headers 'Content-Type=application/json' --body "@$file" | Out-Null
    } finally { Remove-Item $file -ErrorAction SilentlyContinue }
}

function Get-OrCreateApp([string]$DisplayName) {
    $appId = az ad app list --display-name $DisplayName --query '[0].appId' -o tsv
    if (-not $appId) {
        Write-Host "Creating app registration '$DisplayName'"
        $appId = az ad app create --display-name $DisplayName --sign-in-audience AzureADMyOrg --query appId -o tsv
    }
    if (-not (az ad sp list --filter "appId eq '$appId'" --query '[0].id' -o tsv)) {
        az ad sp create --id $appId | Out-Null
    }
    return $appId
}

# ── Context ─────────────────────────────────────────────────────────────────
$account = az account show --query '{sub:id, tenant:tenantId}' -o json | ConvertFrom-Json
gh auth status | Out-Null
$rgLocation = az group show -n $ResourceGroup --query location -o tsv
Write-Host "Subscription $($account.sub), tenant $($account.tenant), RG $ResourceGroup ($rgLocation)"

# ── 1. Resource providers ───────────────────────────────────────────────────
foreach ($ns in 'Microsoft.Web', 'Microsoft.Sql', 'Microsoft.KeyVault', 'Microsoft.Storage', 'Microsoft.Network',
                'Microsoft.Insights', 'Microsoft.OperationalInsights', 'Microsoft.ManagedIdentity') {
    az provider register --namespace $ns --wait | Out-Null
}

# ── 2. GitHub Actions deploy identity (OIDC) ────────────────────────────────
$deployId = 'id-smartserve-github-dev'
$identity = az identity create -g $ResourceGroup -n $deployId -l $rgLocation --query '{clientId:clientId, principalId:principalId}' -o json | ConvertFrom-Json
$owner, $repoName = $Repo -split '/'
$ids = gh api "repos/$Repo" --jq '"\(.owner.id) \(.id)"'
$ownerId, $repoId = $ids -split ' '
# GitHub issues either the classic subject or the newer one that embeds owner/repo IDs.
$subjects = @{
    'github-env-dev'     = "repo:${Repo}:environment:$envName"
    'github-env-dev-ids' = "repo:$owner@$ownerId/$repoName@${repoId}:environment:$envName"
}
$existing = az identity federated-credential list -g $ResourceGroup --identity-name $deployId --query '[].name' -o tsv
foreach ($name in $subjects.Keys) {
    if ($existing -notcontains $name) {
        az identity federated-credential create -g $ResourceGroup --identity-name $deployId -n $name `
            --issuer 'https://token.actions.githubusercontent.com' `
            --subject $subjects[$name] `
            --audiences 'api://AzureADTokenExchange' | Out-Null
    }
}
$rgId = az group show -n $ResourceGroup --query id -o tsv
# Bicep creates Key Vault/Storage role assignments, hence RBAC Administrator alongside Contributor.
foreach ($role in 'Contributor', 'Role Based Access Control Administrator') {
    if (-not (az role assignment list --assignee $identity.principalId --scope $rgId --role $role --query '[0].id' -o tsv)) {
        az role assignment create --assignee-object-id $identity.principalId --assignee-principal-type ServicePrincipal `
            --role $role --scope $rgId | Out-Null
    }
}

# ── 3. Entra ID app registrations ───────────────────────────────────────────
$apiAppId = Get-OrCreateApp 'SmartServe API (dev)'
$apiApp = az ad app show --id $apiAppId -o json | ConvertFrom-Json
if (-not $apiApp.api.oauth2PermissionScopes) {
    $roles = 'Employee', 'Manager', 'SecurityReviewer', 'ItAdmin', 'AppAdmin', 'Auditor' | ForEach-Object {
        @{ id = [guid]::NewGuid(); value = $_; displayName = $_; description = "SmartServe $_";
           allowedMemberTypes = @('User'); isEnabled = $true }
    }
    Invoke-Graph PATCH "https://graph.microsoft.com/v1.0/applications/$($apiApp.id)" @{
        identifierUris = @("api://$apiAppId")
        appRoles       = @($roles)
        api            = @{
            requestedAccessTokenVersion = 2
            oauth2PermissionScopes      = @(@{
                id = [guid]::NewGuid(); value = 'access_as_user'; type = 'User'; isEnabled = $true
                adminConsentDisplayName = 'Access SmartServe API'; adminConsentDescription = 'Access the SmartServe API as the signed-in user.'
                userConsentDisplayName  = 'Access SmartServe';     userConsentDescription  = 'Access SmartServe on your behalf.'
            })
        }
    }
    $apiApp = az ad app show --id $apiAppId -o json | ConvertFrom-Json
}
$scopeId = ($apiApp.api.oauth2PermissionScopes | Where-Object value -eq 'access_as_user').id
$apiSpId = az ad sp list --filter "appId eq '$apiAppId'" --query '[0].id' -o tsv

$me = az ad signed-in-user show --query id -o tsv
$employeeRoleId = ($apiApp.appRoles | Where-Object value -eq 'Employee').id
$assigned = az rest --method GET --uri "https://graph.microsoft.com/v1.0/servicePrincipals/$apiSpId/appRoleAssignedTo" `
    --query "value[?principalId=='$me' && appRoleId=='$employeeRoleId'].id" -o tsv
if (-not $assigned) {
    Invoke-Graph POST "https://graph.microsoft.com/v1.0/servicePrincipals/$apiSpId/appRoleAssignedTo" @{
        principalId = $me; resourceId = $apiSpId; appRoleId = $employeeRoleId
    }
}

$spaAppId = Get-OrCreateApp 'SmartServe Web (dev)'
$spaObjectId = az ad app show --id $spaAppId --query id -o tsv

# Same naming as infra/main.bicep, evaluated by ARM without creating any resources.
$nameTemplate = New-TemporaryFile
@{
    '$schema'      = 'https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#'
    contentVersion = '1.0.0.0'
    resources      = @()
    outputs        = @{ webHost = @{ type = 'string'; value = "[format('smartserve-dev-web-{0}.azurewebsites.net', uniqueString(resourceGroup().id, 'dev'))]" } }
} | ConvertTo-Json -Depth 5 | Set-Content -Path $nameTemplate -Encoding utf8
try {
    $webHost = az deployment group create -g $ResourceGroup -n smartserve-dev-names --template-file $nameTemplate `
        --query properties.outputs.webHost.value -o tsv
} finally { Remove-Item $nameTemplate -ErrorAction SilentlyContinue }
$webUrl = "https://$webHost"

Invoke-Graph PATCH "https://graph.microsoft.com/v1.0/applications/$spaObjectId" @{
    spa                    = @{ redirectUris = @($webUrl, 'http://localhost:5173') }
    requiredResourceAccess = @(@{ resourceAppId = $apiAppId; resourceAccess = @(@{ id = $scopeId; type = 'Scope' }) })
}

# ── 4. GitHub environment, secrets, variables ───────────────────────────────
gh api -X PUT "repos/$Repo/environments/$envName" | Out-Null
$secrets = @{
    AZURE_CLIENT_ID          = $identity.clientId
    AZURE_TENANT_ID          = $account.tenant
    AZURE_SUBSCRIPTION_ID    = $account.sub
    AZURE_RESOURCE_GROUP_DEV = $ResourceGroup
}
foreach ($k in $secrets.Keys) { gh secret set $k --repo $Repo --env $envName --body $secrets[$k] }
gh variable set ENTRA_API_CLIENT_ID --repo $Repo --env $envName --body $apiAppId
gh variable set ENTRA_SPA_CLIENT_ID --repo $Repo --env $envName --body $spaAppId

if ($RunWorkflow) {
    gh workflow run deploy-dev.yml --repo $Repo --ref main
    Write-Host 'Started "Deploy — DEV". Follow it with: gh run watch'
}

Write-Host ''
Write-Host "Setup complete. The 'Deploy — DEV' pipeline now provisions and deploys on every push to main."
Write-Host "Web (after the pipeline runs): $webUrl"
Write-Host "Entra API app $apiAppId, SPA app $spaAppId; you have the Employee role."
