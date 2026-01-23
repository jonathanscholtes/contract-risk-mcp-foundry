metadata description = 'Create an Azure Cosmos DB account.'

param name string
param location string = resourceGroup().location
param tags object = {}

@description('Enables serverless for this account. Defaults to false.')
param enableServerless bool = false

@description('Disables key-based authentication. Defaults to false.')
param disableKeyBasedAuth bool = false

@description('Enables vector search for this account. Defaults to false.')
param enableVectorSearch bool = false

@allowed(['GlobalDocumentDB', 'MongoDB', 'Parse'])
param kind string = 'GlobalDocumentDB' 

param identityName string


resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing= {
  name: identityName
}


resource account 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: name
  location: location
  tags: tags
  kind: kind
  properties: {
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    apiProperties: (kind == 'MongoDB')
      ? {
          serverVersion: '4.2'
        }
      : {}
    disableLocalAuth: false
    capabilities: union(
      (enableServerless)
        ? [
            {
              name: 'EnableServerless'
            }
          ]
        : [],
      (enableVectorSearch)
        ? [
            {
              name: 'EnableNoSQLVectorSearch'
            }
          ]
        : []
    )
  }
}

// Deterministic GUID for role definition
var roleDefinitionGuid = guid('sql-role-definition', account.name, managedIdentity.name)

// Deterministic GUID for role assignment
var roleAssignmentGuid = guid('sql-role-assignment', account.name, managedIdentity.name)





resource cosmosDbRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2024-11-15' = {
  parent: account  
  name: roleDefinitionGuid
  properties: {
    roleName: 'My Read Write Role'
    type: 'CustomRole'
    assignableScopes: [
      account.id
    ]
    permissions: [
      {
        dataActions: [
          'Microsoft.DocumentDB/databaseAccounts/readMetadata'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/read'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/create'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/replace'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/upsert'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/delete'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/executeQuery'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/readChangeFeed'
        ]
        notDataActions: []
      }
    ]
  }
}

resource cosmosDbRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = {
  parent: account
  name: roleAssignmentGuid
  properties: {
    roleDefinitionId: cosmosDbRoleDefinition.id
    principalId: managedIdentity.properties.principalId
    scope: account.id
  }
}

output endpoint string = account.properties.documentEndpoint
output name string = account.name
