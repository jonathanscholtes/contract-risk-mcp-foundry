@description('Name of the Azure Container Registry used to store and manage container images')
param containerRegistryName string

@description('Azure region where all resources will be deployed (e.g., "eastus")')
param location string

@description('User Object ID for RBAC assignment')
param userObjectId string

@description('User-assigned managed identity resource ID')
param managedIdentityId string


module akscluster 'aks.bicep' = {
  name: 'akscluster'
  params: {
    clusterName: 'aievacluster'
    location: location
    userObjectId: userObjectId
    managedIdentityId: managedIdentityId
  }
}

module containerregistry 'registry/container-registry.bicep' = {
  name: 'containerregistry'
  params: {
    containerRegistryName: containerRegistryName
    location: location
    aksPrincipalId: akscluster.outputs.aksPrincipalId
  }
}



output containerRegistryID string = containerregistry.outputs.containerRegistryID
output containerRegistryName string = containerregistry.outputs.containerRegistryName
output aksName string = akscluster.outputs.aksName
output aksPrincipalId string = akscluster.outputs.aksPrincipalId
