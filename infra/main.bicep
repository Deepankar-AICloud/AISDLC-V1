// ---------------------------------------------------------------------------
// SmartServe — environment infrastructure (per environment: dev/staging/prod)
// Managed Identity + Key Vault references; no secrets in code. App Service with
// a staging slot for the API to support slot-swap production promotion.
// ---------------------------------------------------------------------------
targetScope = 'resourceGroup'

@description('Environment name: dev | staging | production')
@allowed([ 'dev', 'staging', 'production' ])
param environmentName string

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Base name used to derive resource names')
param appBaseName string = 'smartserve'

@description('SQL administrator login (password supplied via Key Vault / secure param)')
param sqlAdminLogin string

@secure()
@description('SQL administrator password — pass via pipeline secret / Key Vault, never hardcode')
param sqlAdminPassword string

@description('Entra ID tenant id for API auth')
param entraTenantId string

@description('Entra ID API application (client) id')
param entraClientId string

@description('Enable zone redundancy / higher SKUs for production')
param isProduction bool = environmentName == 'production'

var suffix = uniqueString(resourceGroup().id, environmentName)
var namePrefix = '${appBaseName}-${environmentName}'

// ── Observability ──────────────────────────────────────────────────────────
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${namePrefix}-law-${suffix}'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: isProduction ? 90 : 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namePrefix}-ai-${suffix}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ── Key Vault (secrets accessed via Managed Identity) ──────────────────────
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: take('${appBaseName}${environmentName}kv${suffix}', 24)
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
  }
}

// ── Azure SQL ───────────────────────────────────────────────────────────────
resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: '${namePrefix}-sql-${suffix}'
  location: location
  properties: {
    administratorLogin: sqlAdminLogin
    administratorLoginPassword: sqlAdminPassword
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
}

resource sqlDb 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: 'SmartServeDb'
  location: location
  sku: isProduction ? { name: 'S1', tier: 'Standard' } : { name: 'Basic', tier: 'Basic' }
  properties: {
    zoneRedundant: isProduction
  }
}

resource sqlAllowAzure 'Microsoft.Sql/servers/firewallRules@2023-08-01-preview' = {
  parent: sqlServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// ── Storage / Blob (supporting documents) ──────────────────────────────────
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: take('${appBaseName}${environmentName}st${suffix}', 24)
  location: location
  sku: { name: isProduction ? 'Standard_ZRS' : 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

// ── App Service Plan ────────────────────────────────────────────────────────
resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${namePrefix}-plan-${suffix}'
  location: location
  sku: {
    name: isProduction ? 'P1v3' : 'B1'
    capacity: 1
  }
  properties: { reserved: true } // Linux
}

var commonAppSettings = [
  { name: 'ApplicationInsights__ConnectionString', value: appInsights.properties.ConnectionString }
  { name: 'AzureAd__TenantId', value: entraTenantId }
  { name: 'AzureAd__ClientId', value: entraClientId }
  { name: 'AzureAd__Instance', value: 'https://login.microsoftonline.com/' }
  { name: 'KeyVault__Uri', value: keyVault.properties.vaultUri }
  { name: 'ConnectionStrings__SmartServeDb', value: 'Server=tcp:${sqlServer.properties.fullyQualifiedDomainName},1433;Database=SmartServeDb;Authentication=Active Directory Managed Identity;Encrypt=True;' }
]

// ── Backend API App Service (system-assigned Managed Identity) ─────────────
resource apiApp 'Microsoft.Web/sites@2023-12-01' = {
  name: '${namePrefix}-api-${suffix}'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'DOTNETCORE|8.0'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      healthCheckPath: '/health'
      appSettings: commonAppSettings
    }
  }
}

// Staging slot for slot-swap production promotion.
resource apiStagingSlot 'Microsoft.Web/sites/slots@2023-12-01' = {
  parent: apiApp
  name: 'staging'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'DOTNETCORE|8.0'
      healthCheckPath: '/health'
      minTlsVersion: '1.2'
      appSettings: commonAppSettings
    }
  }
}

// ── Frontend App Service ────────────────────────────────────────────────────
resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: '${namePrefix}-web-${suffix}'
  location: location
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'NODE|20-lts'
      minTlsVersion: '1.2'
    }
  }
}

// ── RBAC: grant the API's managed identity access to Key Vault & Storage ───
resource kvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, apiApp.id, 'kv-secrets-user')
  scope: keyVault
  properties: {
    // Key Vault Secrets User
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: apiApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource blobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, apiApp.id, 'blob-contributor')
  scope: storage
  properties: {
    // Storage Blob Data Contributor
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: apiApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output apiAppName string = apiApp.name
output webAppName string = webApp.name
output apiUrl string = 'https://${apiApp.properties.defaultHostName}'
output webUrl string = 'https://${webApp.properties.defaultHostName}'
output appInsightsConnectionString string = appInsights.properties.ConnectionString
