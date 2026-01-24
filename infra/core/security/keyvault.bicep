param location string
param keyVaultName string



resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    createMode: 'default'
    publicNetworkAccess: 'enabled'
    enabledForDeployment: false
    enabledForDiskEncryption: false
    enabledForTemplateDeployment: false
    enableSoftDelete: false
    enableRbacAuthorization: true
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
  }
}

// Store RabbitMQ credentials
resource rabbitmqUsername 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: 'rabbitmq-username'
  properties: {
    value: 'riskuser'
  }
}

resource rabbitmqPassword 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: 'rabbitmq-password'
  properties: {
    value: uniqueString(keyVault.id, 'rabbitmq')
  }
}


output keyVaultId string = keyVault.id
output keyVaultUri string = keyVault.properties.vaultUri
output keyVaultName string = keyVaultName
