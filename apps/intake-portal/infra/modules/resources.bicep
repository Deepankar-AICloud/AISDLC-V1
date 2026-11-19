targetScope = 'resourceGroup'

@description('Location for all resources.')
param location string = resourceGroup().location

@description('Tags applied to every resource.')
param tags object = {}

@description('Unique suffix for globally unique resource names.')
param resourceToken string

@description('Object ID of the identity running azd (gets AcrPush). Empty skips the assignment.')
param principalId string = ''

param principalType string = 'User'

@secure()
param studioPassword string

@secure()
param sessionSecret string

@secure()
param copilotGithubToken string = ''

@description('Deployed image (registry/repository:tag). Empty uses a placeholder until azd deploys.')
param studioImageName string = ''

param enableCodeStage bool = true

var serviceName = 'studio'
var webAppName = 'app-studio-${resourceToken}'
// Placeholder so the site can be created before azd builds and pushes the Studio image.
var placeholderImage = 'mcr.microsoft.com/appsvc/staticsite:latest'

module logAnalytics 'br/public:avm/res/operational-insights/workspace:0.16.2' = {
  name: 'studio-log-analytics'
  params: {
    name: 'log-studio-${resourceToken}'
    location: location
    tags: tags
    skuName: 'PerGB2018'
    dataRetention: 30
  }
}

// Identity the web app uses to pull from the registry (no registry passwords).
module pullIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.6.0' = {
  name: 'studio-pull-identity'
  params: {
    name: 'id-studio-${resourceToken}'
    location: location
    tags: tags
  }
}

module registry 'br/public:avm/res/container-registry/registry:0.13.2' = {
  name: 'studio-registry'
  params: {
    name: 'acrstudio${resourceToken}'
    location: location
    tags: tags
    acrSku: 'Basic'
    acrAdminUserEnabled: false
    anonymousPullEnabled: false
    // azd signs in to ACR with an ARM-audience Entra token; RBAC (AcrPush/AcrPull) is still required.
    azureADAuthenticationAsArmPolicyStatus: 'enabled'
    roleAssignments: concat(
      [
        {
          principalId: pullIdentity.outputs.principalId
          principalType: 'ServicePrincipal'
          roleDefinitionIdOrName: 'AcrPull'
        }
      ],
      empty(principalId)
        ? []
        : [
            {
              principalId: principalId
              principalType: principalType
              roleDefinitionIdOrName: 'AcrPush'
            }
          ]
    )
    diagnosticSettings: [
      {
        workspaceResourceId: logAnalytics.outputs.resourceId
      }
    ]
  }
}

module appServicePlan 'br/public:avm/res/web/serverfarm:0.7.1' = {
  name: 'studio-plan'
  params: {
    name: 'asp-studio-${resourceToken}'
    location: location
    tags: tags
    kind: 'linux'
    reserved: true
    skuName: 'P1v3'
    // Jobs are files plus an in-process runner: exactly one instance.
    skuCapacity: 1
    zoneRedundant: false
  }
}

module webApp 'br/public:avm/res/web/site:0.24.0' = {
  name: 'studio-web-app'
  params: {
    name: webAppName
    location: location
    tags: union(tags, { 'azd-service-name': serviceName })
    kind: 'app,linux,container'
    serverFarmResourceId: appServicePlan.outputs.resourceId
    httpsOnly: true
    clientAffinityEnabled: false
    managedIdentities: {
      userAssignedResourceIds: [
        pullIdentity.outputs.resourceId
      ]
    }
    siteConfig: {
      linuxFxVersion: 'DOCKER|${empty(studioImageName) ? placeholderImage : studioImageName}'
      acrUseManagedIdentityCreds: true
      acrUserManagedIdentityID: pullIdentity.outputs.clientId
      alwaysOn: true
      healthCheckPath: '/healthz'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      http20Enabled: true
      remoteDebuggingEnabled: false
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
        workspaceResourceId: logAnalytics.outputs.resourceId
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

// Separate from the module so PUBLIC_BASE_URL can use the site's real default host name.
resource appSettings 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: site
  name: 'appsettings'
  properties: union(
    {
      WEBSITES_PORT: '8000'
      // Persistent /home share: jobs, workspaces and the agent's HOME survive restarts.
      WEBSITES_ENABLE_APP_SERVICE_STORAGE: 'true'
      // Kept modest: on a fresh environment the first provision runs a placeholder image that listens on
      // 8080, so its warm-up probe on 8000 never succeeds and blocks the first deploy for this long.
      WEBSITES_CONTAINER_START_TIME_LIMIT: '600'
      APP_ENV: 'production'
      PUBLIC_BASE_URL: 'https://${webApp.outputs.defaultHostname}'
      DATA_DIR: '/home/studio-data'
      // App Service rejects an app setting named HOME; the container start command exports it.
      STUDIO_HOME: '/home/studio'
      STUDIO_USERNAME: 'admin'
      STUDIO_PASSWORD: studioPassword
      SESSION_SECRET: sessionSecret
      ENABLE_CODE_STAGE: enableCodeStage ? 'true' : 'false'
      USE_LLM: empty(copilotGithubToken) ? 'false' : 'true'
      MAX_CONCURRENT_RUNS: '1'
      STAGE_TIMEOUT_SECONDS: '3600'
    },
    empty(copilotGithubToken) ? {} : { COPILOT_GITHUB_TOKEN: copilotGithubToken }
  )
}

output registryLoginServer string = registry.outputs.loginServer
output registryName string = registry.outputs.name
output logAnalyticsWorkspaceId string = logAnalytics.outputs.resourceId
output webAppName string = webApp.outputs.name
output webAppUrl string = 'https://${webApp.outputs.defaultHostname}'
