targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name representing the deployment environment (e.g., "dev", "test", "prod", "lab"); used to generate a short, unique hash for each resource')
param environmentName string


@minLength(1)
@maxLength(64)
@description('Name used to identify the project; also used to generate a short, unique hash for each resource')
param projectName string

@description('Token or string used to uniquely identify this resource deployment (e.g., build ID, commit hash)')
param resourceToken string


@minLength(1)
@description('Azure region where all resources will be deployed (e.g., "eastus")')
param location string

@minLength(1)
@description('Azure region where all AI resources will be deployed (e.g., "eastus")')
param AIlocation string

@description('Azure AD Object ID of the deploying user for CosmosDB access')
param userObjectId string

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${projectName}-${environmentName}-${location}-${resourceToken}'
  location: location
}

// Create managed identity first
module managedIdentityModule 'core/security/managed-identity.bicep' = {
  name: 'managed-identity'
  scope: resourceGroup
  params: {
    name: 'id-${projectName}-${environmentName}'
    location: location
  }
}

// Create Key Vault
module keyVaultModule 'core/security/keyvault.bicep' = {
  name: 'keyVault'
  scope: resourceGroup
  params: {
    location: location
    keyVaultName: 'kv${projectName}${resourceToken}'
  }
}

module monitor 'core/monitor/main.bicep' = { 
  name:'monitor'
  scope: resourceGroup
  params:{ 
   location:location 
   logAnalyticsName: 'log-${projectName}-${environmentName}-${resourceToken}'
   applicationInsightsName: 'appi-${projectName}-${environmentName}-${resourceToken}'
  }
}


module data 'core/data/main.bicep' = {
  name: 'data'
  scope: resourceGroup
  params:{
    projectName:projectName
    resourceToken:resourceToken
    environmentName:environmentName
    location: location
    identityName:managedIdentityModule.outputs.managedIdentityName
    userObjectId: userObjectId
  }
}

module platform 'core/platform/main.bicep' = { 
  name: 'platform'
  scope: resourceGroup
  params: { 
    containerRegistryName: 'cr${projectName}${environmentName}${resourceToken}'
    location:location
    userObjectId: userObjectId
    managedIdentityId: managedIdentityModule.outputs.managedIdentityId
    managedIdentityName: managedIdentityModule.outputs.managedIdentityName
  }
}

// Configure Key Vault access after AKS is created
module securityRoles 'core/security/security-roles.bicep' = {
  name: 'security-roles'
  scope: resourceGroup
  params: {
    keyVaultName: 'kv${projectName}${resourceToken}'
    managedIdentityName: 'id-${projectName}-${environmentName}'
    userObjectId: userObjectId
    keyVaultSecretsProviderObjectId: platform.outputs.keyVaultSecretsProviderObjectId
  }
  dependsOn: [keyVaultModule, managedIdentityModule, platform]
}


module ai 'core/ai/main.bicep' = {
  name: 'ai'
  scope: resourceGroup
  params: { 
    projectName:projectName
    environmentName:environmentName
    resourceToken:resourceToken
    location: AIlocation
    appInsightsName: monitor.outputs.applicationInsightsName
    identityName:managedIdentityModule.outputs.managedIdentityName
    storageAccountId:data.outputs.storageAccountId
  searchServicename: 'srch-${projectName}-${environmentName}-${resourceToken}'
  }
}







output managedIdentityName string = managedIdentityModule.outputs.managedIdentityName
output managedIdentityClientId string = managedIdentityModule.outputs.managedIdentityClientId
output resourceGroupName string = resourceGroup.name
output storageAccountName string = data.outputs.storageAccountName 
output logAnalyticsWorkspaceName string = monitor.outputs.logAnalyticsWorkspaceName
output applicationInsightsName string = monitor.outputs.applicationInsightsName
output keyVaultName string = keyVaultModule.outputs.keyVaultName
output OpenAIEndPoint string = ai.outputs.OpenAIEndPoint 
output aiProjectEndpoint string = ai.outputs.aiProjectEndpoint
output cosmosdbEndpoint string = data.outputs.cosmosdbEndpoint
output containerRegistryName string = platform.outputs.containerRegistryName
output aksName string = platform.outputs.aksName
