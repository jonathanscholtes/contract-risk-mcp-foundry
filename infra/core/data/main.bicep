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

var storageAccountName ='sa${projectName}${resourceToken}'

module storage 'storage/main.bicep' = {
name: 'storage'
params:{
  identityName:identityName
   location:location
   storageAccountName:storageAccountName

}
}

module cosmosDb 'cosmosdb/main.bicep' = {
  name: 'cosmosDb'
 
  params: {
    accountName: 'cosmos-${projectName}-${environmentName}-${resourceToken}'
    location: location
    databaseName: 'audit-poc'
    identityName: identityName
    containers: [
  {
    name: 'vendors' // Container for storing chat sessions and messages (chat history)
    partitionKeyPaths: [
      '/engagement_id' 
    ]
    ttlValue: 0 // Time-to-live (TTL) for automatic deletion of data after 24 hours (86400 seconds)
    indexingPolicy: {
      automatic: true // Automatically index new data
      indexingMode: 'consistent' // Ensure data is indexed immediately
      includedPaths: [
        {
          path: '/engagement_id/?' 
        }
      ]
      excludedPaths: [
        {
          path: '/*' // Exclude all other paths from indexing
        }
      ]
    }
    vectorEmbeddingPolicy: {
      vectorEmbeddings: [] // Placeholder for future vector embedding configuration
    }
  }
  {
    name: 'invoices' // Container for storing chat sessions and messages (chat history)
    partitionKeyPaths: [
      '/engagement_id' 
    ]
    ttlValue: 0 // Time-to-live (TTL) for automatic deletion of data after 24 hours (86400 seconds)
    indexingPolicy: {
      automatic: true // Automatically index new data
      indexingMode: 'consistent' // Ensure data is indexed immediately
      includedPaths: [
        {
          path: '/engagement_id/?' 
        }
      ]
      excludedPaths: [
        {
          path: '/*' // Exclude all other paths from indexing
        }
      ]
    }
    vectorEmbeddingPolicy: {
      vectorEmbeddings: [] // Placeholder for future vector embedding configuration
    }
  }
  {
    name: 'payments' // Container for storing chat sessions and messages (chat history)
    partitionKeyPaths: [
      '/engagement_id' 
    ]
    ttlValue: 0 // Time-to-live (TTL) for automatic deletion of data after 24 hours (86400 seconds)
    indexingPolicy: {
      automatic: true // Automatically index new data
      indexingMode: 'consistent' // Ensure data is indexed immediately
      includedPaths: [
        {
          path: '/engagement_id/?' 
        }
      ]
      excludedPaths: [
        {
          path: '/*' // Exclude all other paths from indexing
        }
      ]
    }
    vectorEmbeddingPolicy: {
      vectorEmbeddings: [] // Placeholder for future vector embedding configuration
    }
  }
 
]
  }
}

output storageAccountName string = storageAccountName
output storageAccountId string = storage.outputs.storageAccountId
output cosmosdbEndpoint string = cosmosDb.outputs.cosmosdbEndpoint
output cosmosdbAccountName string = cosmosDb.outputs.accountName

