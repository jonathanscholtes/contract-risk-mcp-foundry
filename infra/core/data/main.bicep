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

@description('Name of the User Assigned Managed Identity to assign to deployed services')
param identityName string

@secure()
@description('Admin password for MongoDB cluster')
@minLength(8)
@maxLength(128)
param mongoAdminPassword string

var storageAccountName = 'sa${projectName}${resourceToken}'

module storage 'storage/main.bicep' = {
  name: 'storage'
  params: {
    identityName: identityName
    location: location
    storageAccountName: storageAccountName
  }
}

module mongoDb 'mongodb/main.bicep' = {
  name: 'mongoDb'
  params: {
    clusterName: 'mongo-${projectName}-${resourceToken}'
    location: location
    tags: {
      environment: environmentName
      project: projectName
    }
    adminPassword: mongoAdminPassword
    serverVersion: '8.0'
    shardCount: 1
    storageSizeGb: 32
    highAvailabilityMode: 'Disabled'
    computeTier: 'M10'
  }
}

output storageAccountName string = storageAccountName
output storageAccountId string = storage.outputs.storageAccountId
output mongoDbClusterName string = mongoDb.outputs.clusterName
output mongoDbUsername string = mongoDb.outputs.adminUsername
output mongoDbConnectionString string = mongoDb.outputs.connectionString
output mongoDbEndpoint string = mongoDb.outputs.endpoint

