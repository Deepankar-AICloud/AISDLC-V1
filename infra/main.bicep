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

@description('Entra ID tenant id for API auth')
param entraTenantId string

@description('Entra ID API application (client) id')
param entraClientId string

@description('Enable zone redundancy / higher SKUs for production')
param isProduction bool = environmentName == 'production'

var suffix = uniqueString(resourceGroup().id, environmentName)
var namePrefix = '${appBaseName}-${environmentName}'
// Deployment slots need Standard or higher; DEV stays on Basic without a slot.
var useStagingSlot = environmentName != 'dev'

// ── API identity (user-assigned so SQL, Key Vault and Storage access exist before the app starts) ──
resource apiIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${namePrefix}-api-id-${suffix}'
  location: location
}

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
    publicNetworkAccess: 'Disabled'
    networkAcls: { defaultAction: 'Deny', bypass: 'AzureServices' }
  }
}

// ── Azure SQL ───────────────────────────────────────────────────────────────
resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: '${namePrefix}-sql-${suffix}'
  location: location
  properties: {
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Disabled'
    // Entra-only auth; the API identity is admin because EF migrations run at startup and need DDL rights.
    administrators: {
      administratorType: 'ActiveDirectory'
      principalType: 'Application'
      login: apiIdentity.name
      sid: apiIdentity.properties.clientId
      tenantId: subscription().tenantId
      azureADOnlyAuthentication: true
    }
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
    publicNetworkAccess: 'Disabled'
    allowSharedKeyAccess: false
  }
}

// ── Private networking (SQL, Key Vault and Storage have public access disabled) ──
resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: '${namePrefix}-vnet-${suffix}'
  location: location
  properties: {
    addressSpace: { addressPrefixes: [ '10.40.0.0/16' ] }
    subnets: [
      {
        name: 'app'
        properties: {
          addressPrefix: '10.40.1.0/24'
          delegations: [ { name: 'web', properties: { serviceName: 'Microsoft.Web/serverFarms' } } ]
        }
      }
      {
        name: 'private-endpoints'
        properties: { addressPrefix: '10.40.2.0/24' }
      }
    ]
  }
}

var appSubnetId = '${vnet.id}/subnets/app'
var peSubnetId = '${vnet.id}/subnets/private-endpoints'

var privateLinks = [
  { name: 'sql', zone: 'privatelink${environment().suffixes.sqlServerHostname}', target: sqlServer.id, group: 'sqlServer' }
  { name: 'kv', zone: 'privatelink.vaultcore.azure.net', target: keyVault.id, group: 'vault' }
]

resource dnsZones 'Microsoft.Network/privateDnsZones@2020-06-01' = [for pl in privateLinks: {
  name: pl.zone
  location: 'global'
}]

resource dnsLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = [for (pl, i) in privateLinks: {
  parent: dnsZones[i]
  name: '${namePrefix}-link'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}]

resource privateEndpoints 'Microsoft.Network/privateEndpoints@2023-11-01' = [for pl in privateLinks: {
  name: '${namePrefix}-${pl.name}-pe-${suffix}'
  location: location
  properties: {
    subnet: { id: peSubnetId }
    privateLinkServiceConnections: [
      { name: pl.name, properties: { privateLinkServiceId: pl.target, groupIds: [ pl.group ] } }
    ]
  }
}]

resource peDnsGroups 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = [for (pl, i) in privateLinks: {
  parent: privateEndpoints[i]
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [ { name: pl.name, properties: { privateDnsZoneId: dnsZones[i].id } } ]
  }
}]

// ── App Service Plan ────────────────────────────────────────────────────────
resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${namePrefix}-plan-${suffix}'
  location: location
  sku: {
    name: isProduction ? 'P1v3' : (useStagingSlot ? 'S1' : 'B1')
    capacity: 1
  }
  properties: { reserved: true } // Linux
}

@description('(proposed) Object id of the Entra user/mailbox the API sends notification email as, via Graph sendMail')
param graphSenderUserId string = ''

var commonAppSettings = [
  { name: 'ApplicationInsights__ConnectionString', value: appInsights.properties.ConnectionString }
  { name: 'AzureAd__TenantId', value: entraTenantId }
  { name: 'AzureAd__ClientId', value: entraClientId }
  { name: 'AzureAd__Instance', value: 'https://login.microsoftonline.com/' }
  { name: 'KeyVault__Uri', value: keyVault.properties.vaultUri }
  { name: 'ConnectionStrings__SmartServeDb', value: 'Server=tcp:${sqlServer.properties.fullyQualifiedDomainName},1433;Database=SmartServeDb;Authentication=Active Directory Managed Identity;User Id=${apiIdentity.properties.clientId};Encrypt=True;' }
  { name: 'Graph__SenderUserId', value: graphSenderUserId }
  // DefaultAzureCredential (Key Vault, Graph) uses this to select the user-assigned identity.
  { name: 'AZURE_CLIENT_ID', value: apiIdentity.properties.clientId }
  { name: 'Cors__AllowedOrigins__0', value: 'https://${webApp.properties.defaultHostName}' }
]

var apiIdentityConfig = {
  type: 'UserAssigned'
  userAssignedIdentities: { '${apiIdentity.id}': {} }
}

// ── Backend API App Service ─────────────────────────────────────────────────
resource apiApp 'Microsoft.Web/sites@2023-12-01' = {
  name: '${namePrefix}-api-${suffix}'
  location: location
  identity: apiIdentityConfig
  dependsOn: [ kvSecretsUser, blobContributor, peDnsGroups, dnsLinks ]
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    virtualNetworkSubnetId: appSubnetId
    vnetRouteAllEnabled: true
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
resource apiStagingSlot 'Microsoft.Web/sites/slots@2023-12-01' = if (useStagingSlot) {
  parent: apiApp
  name: 'staging'
  location: location
  identity: apiIdentityConfig
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    virtualNetworkSubnetId: appSubnetId
    vnetRouteAllEnabled: true
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
      linuxFxVersion: 'NODE|22-lts'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      // Serve the static Vite build with client-side routing fallback.
      appCommandLine: 'pm2 serve /home/site/wwwroot --no-daemon --spa'
    }
  }
}

// ── RBAC: grant the API's managed identity access to Key Vault & Storage ───
resource kvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, apiIdentity.id, 'kv-secrets-user')
  scope: keyVault
  properties: {
    // Key Vault Secrets User
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: apiIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource blobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, apiIdentity.id, 'blob-contributor')
  scope: storage
  properties: {
    // Storage Blob Data Contributor
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: apiIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// (proposed) Microsoft Graph application permissions (Mail.Send, User.Read.All, User.ReadBasic.All)
// for the API's managed identity (apiIdentity) cannot be expressed as a standard Microsoft.Authorization
// roleAssignment — they are Microsoft Graph app-role assignments that require directory-level
// admin consent. Grant them out-of-band post-deployment, e.g.:
//   az ad app permission admin-consent ... / or an AzureCLI deploymentScript invoking
//   POST https://graph.microsoft.com/v1.0/servicePrincipals/{apiApp-principal-id}/appRoleAssignments
// against the well-known Microsoft Graph service principal (appId 00000003-0000-0000-c000-000000000000),
// run by a principal already holding Application.ReadWrite.All / AppRoleAssignment.ReadWrite.All.
// Not automated here to avoid requiring elevated Graph-admin credentials inside this template.

output apiAppName string = apiApp.name
output webAppName string = webApp.name
output apiUrl string = 'https://${apiApp.properties.defaultHostName}'
output webUrl string = 'https://${webApp.properties.defaultHostName}'
output appInsightsConnectionString string = appInsights.properties.ConnectionString
