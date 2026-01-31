
@description('Name of the Azure AI Foundry  instance')
param accountName string


resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: accountName
}



resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  name: 'gpt-4o'
  sku: {
    capacity: 250
    name: 'GlobalStandard'
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-11-20'
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
    raiPolicyName: 'Microsoft.DefaultV2'
  }

}

resource gpt52Deployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  name: 'gpt-5.2-chat'
  sku: {
    name: 'GlobalStandard'
    capacity: 150
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5.2-chat'
      version: '2025-12-11'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  dependsOn: [gpt4oDeployment]
}




