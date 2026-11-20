targetScope = 'resourceGroup'

// Intake Portal web app on the shared Studio plan, registry identity and Log Analytics workspace.
// No sign-in page (AUTH_MODE=open): the site is reachable only from the allow-listed IPs.

param location string = resourceGroup().location
param tags object = {}

@description('Globally unique web app name (becomes <name>.azurewebsites.net).')
param webAppName string

param serverFarmResourceId string
param pullIdentityResourceId string
param pullIdentityClientId string
param logAnalyticsWorkspaceId string

@description('Deployed image (registry/repository:tag). Empty uses a placeholder until azd deploys.')
param imageName string = ''

@minLength(1)
@description('IPv4/IPv6 addresses or CIDR ranges allowed to reach the portal. Everything else is denied.')
param allowedIpAddresses array

param githubRepository string
param githubAppId string
param githubAppClientId string

@secure()
param githubAppClientSecret string

@secure()
@description('GitHub App private key PEM, base64-encoded so it survives azd env files intact.')
param githubAppPrivateKeyBase64 string

@secure()
param githubWebhookSecret string

@secure()
@description('Fernet key (urlsafe base64, 32 bytes) used to encrypt stored GitHub user tokens.')
param tokenEncryptionKey string

@secure()
param sessionSecret string

var serviceName = 'portal'
var placeholderImage = 'mcr.microsoft.com/appsvc/staticsite:latest'
// The portal reads "\n" escapes in GITHUB_APP_PRIVATE_KEY, which keeps the app setting single-line.
var privateKeyEscaped = replace(replace(base64ToString(githubAppPrivateKeyBase64), '\r', ''), '\n', '\\n')

var ipRestrictions = [
  for (ip, i) in allowedIpAddresses: {
    name: 'allow-${i}'
    action: 'Allow'
    priority: 100 + i
    ipAddress: contains(ip, '/') ? ip : '${ip}/32'
  }
]

module webApp 'br/public:avm/res/web/site:0.24.0' = {
  name: 'portal-web-app'
  params: {
    name: webAppName
    location: location
    tags: union(tags, { 'azd-service-name': serviceName })
    kind: 'app,linux,container'
    serverFarmResourceId: serverFarmResourceId
    httpsOnly: true
    clientAffinityEnabled: false
    managedIdentities: {
      userAssignedResourceIds: [
        pullIdentityResourceId
      ]
    }
    siteConfig: {
      linuxFxVersion: 'DOCKER|${empty(imageName) ? placeholderImage : imageName}'
      acrUseManagedIdentityCreds: true
      acrUserManagedIdentityID: pullIdentityClientId
      alwaysOn: true
      healthCheckPath: '/healthz'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      http20Enabled: true
      remoteDebuggingEnabled: false
      ipSecurityRestrictionsDefaultAction: 'Deny'
      ipSecurityRestrictions: ipRestrictions
      scmIpSecurityRestrictionsUseMain: true
      scmIpSecurityRestrictionsDefaultAction: 'Deny'
    }
    basicPublishingCredentialsPolicies: [
      {
        name: 'ftp'
        allow: false
      }
      {
        name: 'scm'
        allow: false
      }
    ]
    configs: [
      {
        name: 'logs'
        properties: {
          applicationLogs: {
            fileSystem: {
              level: 'Information'
            }
          }
          httpLogs: {
            fileSystem: {
              enabled: true
              retentionInDays: 7
              retentionInMb: 35
            }
          }
          detailedErrorMessages: {
            enabled: true
          }
          failedRequestsTracing: {
            enabled: false
          }
        }
      }
    ]
    diagnosticSettings: [
      {
        workspaceResourceId: logAnalyticsWorkspaceId
        logCategoriesAndGroups: [
          {
            category: 'AppServiceConsoleLogs'
          }
          {
            category: 'AppServiceHTTPLogs'
          }
          {
            category: 'AppServicePlatformLogs'
          }
          {
            category: 'AppServiceIPSecAuditLogs'
          }
        ]
        metricCategories: [
          {
            category: 'AllMetrics'
          }
        ]
      }
    ]
  }
}

resource site 'Microsoft.Web/sites@2024-04-01' existing = {
  name: webAppName
  dependsOn: [
    webApp
  ]
}

resource appSettings 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: site
  name: 'appsettings'
  properties: {
    WEBSITES_PORT: '8000'
    WEBSITES_ENABLE_APP_SERVICE_STORAGE: 'true'
    // The first provision runs a placeholder image on 8080, so keep its warm-up wait short.
    WEBSITES_CONTAINER_START_TIME_LIMIT: '600'
    APP_ENV: 'production'
    AUTH_MODE: 'open'
    OPEN_MODE_NETWORK_RESTRICTED: 'true'
    GITHUB_MODE: 'app'
    PUBLIC_BASE_URL: 'https://${webApp.outputs.defaultHostname}'
    DATA_DIR: '/home/portal-data'
    DATABASE_URL: 'sqlite:////home/portal-data/portal.db'
    EXTRACTION_ISOLATION: 'process'
    GITHUB_REPOSITORY: githubRepository
    GITHUB_APP_ID: githubAppId
    GITHUB_APP_CLIENT_ID: githubAppClientId
    GITHUB_APP_CLIENT_SECRET: githubAppClientSecret
    GITHUB_APP_PRIVATE_KEY: privateKeyEscaped
    GITHUB_WEBHOOK_SECRET: githubWebhookSecret
    TOKEN_ENCRYPTION_KEY: tokenEncryptionKey
    SESSION_SECRET: sessionSecret
  }
}

output webAppName string = webApp.outputs.name
output webAppUrl string = 'https://${webApp.outputs.defaultHostname}'
