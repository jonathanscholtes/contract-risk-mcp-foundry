metadata description = 'Create Azure DocumentDB for contract and risk data storage.'

@description('Cluster name')
@minLength(8)
@maxLength(40)
param clusterName string

@description('Location for the cluster.')
param location string 

@description('Tags for the cluster')
param tags object = {}

@description('Username for admin user')
param adminUsername string = 'mongoadmin'

@secure()
@description('Password for admin user')
@minLength(8)
@maxLength(128)
param adminPassword string

@description('Server version')
@allowed(['5.0', '6.0', '7.0', '8.0'])
param serverVersion string = '8.0'

@description('Number of shards')
@minValue(1)
@maxValue(12)
param shardCount int = 1

@description('Storage size in GB')
@minValue(32)
@maxValue(16384)
param storageSizeGb int = 32

@description('High availability mode')
@allowed(['Disabled', 'SameZone', 'ZoneRedundant'])
param highAvailabilityMode string = 'Disabled'

@description('Compute tier')
@allowed(['M10', 'M20', 'M30', 'M40', 'M50', 'M60', 'M80'])
param computeTier string = 'M10'

resource cluster 'Microsoft.DocumentDB/mongoClusters@2025-09-01' = {
  name: clusterName
  location: location
  tags: tags
  properties: {
    administrator: {
      userName: adminUsername
      password: adminPassword
    }
    serverVersion: serverVersion
    sharding: {
      shardCount: shardCount
    }
    storage: {
      sizeGb: storageSizeGb
    }
    highAvailability: {
      targetMode: highAvailabilityMode
    }
    compute: {
      tier: computeTier
    }
  }
}

// Allow access from Azure services
resource firewallRules 'Microsoft.DocumentDB/mongoClusters/firewallRules@2025-09-01' = {
  parent: cluster
  name: 'AllowAllAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// Outputs
output clusterName string = cluster.name
output clusterId string = cluster.id
output adminUsername string = adminUsername
// Note: Password is URL-encoded in connection string for special characters
// Using replace() for common special characters - for production, consider using deployment script for full URL encoding
var encodedPassword = replace(replace(replace(replace(replace(replace(replace(replace(adminPassword, '@', '%40'), '!', '%21'), '#', '%23'), '$', '%24'), '%', '%25'), '^', '%5E'), '&', '%26'), '*', '%2A')
output connectionString string = 'mongodb+srv://${adminUsername}:${encodedPassword}@${cluster.name}.mongocluster.cosmos.azure.com/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000'
output endpoint string = '${cluster.name}.mongocluster.cosmos.azure.com'
