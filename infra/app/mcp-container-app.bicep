@description('Base name of the Azure Container App to be deployed')
param containerAppBaseName string

@description('Azure region where the resources will be deployed (e.g., "eastus")')
param location string

@description('Name of the User Assigned Managed Identity to be used by the Container App')
param managedIdentityName string

@description('Name of the Log Analytics Workspace for monitoring and diagnostics')
param logAnalyticsWorkspaceName string

@description('Name of the Azure Container Registry for storing and managing container images')
param containerRegistryName string

param cosmosDBEndpoint string
param cosmosDBDatabaseName string
param cosmosDBContainerName string


resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2021-06-01' existing = {
  name: logAnalyticsWorkspaceName
}


resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: managedIdentityName
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2024-11-01-preview' existing = {
  name: containerRegistryName
}

// Container App Environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: 'cae-${containerAppBaseName}'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: listKeys(logAnalyticsWorkspace.id, logAnalyticsWorkspace.apiVersion).primarySharedKey
      }
    }
  }
}

// Weather Container App
resource mcpApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'ca-mcp-${containerAppBaseName}'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 80
        transport: 'auto'
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: managedIdentity.id
           
        }
      ]
    }
    template: {
     containers: [
      
        {
          name: 'audit'
          image: '${containerRegistry.properties.loginServer}/audit-mcp:latest'
          env: [
            { name: 'SERVICE_NAME', value: 'audit' }
            { name: 'MCP_PORT', value: '80' }

            { name: 'COSMOS_ENDPOINT', value: cosmosDBEndpoint }
            { name: 'COSMOS_DATABASE', value: cosmosDBDatabaseName }
            { name: 'COSMOS_CONTAINER', value: cosmosDBContainerName }

            {
            name: 'AZURE_CLIENT_ID'
            value: managedIdentity.properties.clientId
          } 
        
          ]
        }        
        
      ]
    }
  }
}
