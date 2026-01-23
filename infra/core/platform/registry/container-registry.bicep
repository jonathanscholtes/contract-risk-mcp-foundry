param containerRegistryName string
param location string

@description('AKS managed identity principal ID for ACR pull access')
param aksPrincipalId string = ''



resource containerRegistry 'Microsoft.ContainerRegistry/registries@2024-11-01-preview' = {
  name: containerRegistryName
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    adminUserEnabled: true
    policies: {
      quarantinePolicy: { status: 'disabled' }
      trustPolicy: { type: 'Notary', status: 'disabled' }
      retentionPolicy: { days: 7, status: 'disabled' }
      exportPolicy: { status: 'enabled' }
      azureADAuthenticationAsArmPolicy: { status: 'enabled' }
      softDeletePolicy: { retentionDays: 7, status: 'disabled' }
    }
    encryption: { status: 'disabled' }
    dataEndpointEnabled: false
    publicNetworkAccess: 'Enabled'  
    networkRuleBypassOptions: 'AzureServices'
    zoneRedundancy: 'Disabled'
    anonymousPullEnabled: false
    metadataSearch: 'Disabled'
  }
}

// AcrPull role definition
var acrPullRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')

// Grant AKS cluster access to pull images from ACR
resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(aksPrincipalId)) {
  name: guid(containerRegistry.id, aksPrincipalId, acrPullRole)
  scope: containerRegistry
  properties: {
    roleDefinitionId: acrPullRole
    principalId: aksPrincipalId
    principalType: 'ServicePrincipal'
  }
}


output containerRegistryID string = containerRegistry.id
output containerRegistryName string = containerRegistry.name
