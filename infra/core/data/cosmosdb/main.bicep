metadata description = 'Create database accounts.'

param accountName string
param databaseName string = 'chatdatabase'

param location string = resourceGroup().location
param tags object = {}

param identityName string

@description('Optional: Azure AD Object ID of the deploying user for CosmosDB access')
param userObjectId string = ''

// Define the database for the chat application
var database = {
  name: databaseName
}

// Define the containers for the database
param containers array = [
  {
    name: 'chathistory' // Container for storing chat sessions and messages (chat history)
    partitionKeyPaths: [
      '/id' 
    ]
    ttlValue: 86400 // Time-to-live (TTL) for automatic deletion of data after 24 hours (86400 seconds)
    indexingPolicy: {
      automatic: true // Automatically index new data
      indexingMode: 'consistent' // Ensure data is indexed immediately
      includedPaths: [
        {
          path: '/sessionId/?' 
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

module cosmosDbAccount 'account.bicep' = {
  name: 'cosmos-db-account'
  params: {
    name: accountName
    location: location
    tags: tags
    enableServerless: true
    enableVectorSearch: true
    identityName: identityName
    userObjectId: userObjectId
  }
}

module cosmosDbDatabase 'database.bicep' = {
  name: 'cosmos-db-database-${database.name}'
  params: {
    name: database.name
    parentAccountName: cosmosDbAccount.outputs.name
    tags: tags
    setThroughput: false
  }
  dependsOn: [cosmosDbAccount]
}

module cosmosDbContainers 'container.bicep' = [
  for (container, _) in containers: {
    name: 'cosmos-db-container-${container.name}'
    params: {
      name: container.name
      parentAccountName: cosmosDbAccount.outputs.name
      parentDatabaseName: cosmosDbDatabase.outputs.name
      tags: tags
      setThroughput: false
      partitionKeyPaths: container.partitionKeyPaths
      indexingPolicy: container.indexingPolicy
      vectorEmbeddingPolicy: container.vectorEmbeddingPolicy
      ttlValue: container.ttlValue
    }
    dependsOn: [cosmosDbDatabase]
  }
]

output cosmosdbEndpoint string = cosmosDbAccount.outputs.endpoint
output accountName string = cosmosDbAccount.outputs.name

output database object = {
  name: cosmosDbDatabase.outputs.name
}
output containers array = [
  for (_, index) in containers: {
    name: cosmosDbContainers[index].outputs.name
  }
]


