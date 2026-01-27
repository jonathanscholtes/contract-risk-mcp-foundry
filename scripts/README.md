# Deployment Scripts

This directory contains modular deployment scripts for the Contract Risk MCP Platform.

## Structure

```
scripts/
├── common/
│   └── DeploymentFunctions.ps1    # Shared utility functions
├── Deploy-Infrastructure.ps1       # Azure resource deployment (Bicep)
├── Deploy-Containers.ps1           # Container image builds (ACR)
├── Deploy-Kubernetes.ps1           # Kubernetes/Helm deployments
├── Deploy-FoundryAgents.ps1        # Foundry agent deployment
└── deploy_foundry_agents.py        # Python agent deployment logic
```

## Usage

### Full End-to-End Deployment

Use the main orchestrator script:

```powershell
.\deploy-new.ps1 -Subscription "<SUBSCRIPTION_ID>" -Location "eastus2"
```

### Modular Deployment

Each phase can be run independently for development, debugging, or updates:

#### 1. Infrastructure Only

```powershell
.\scripts\Deploy-Infrastructure.ps1 `
    -Subscription "<SUBSCRIPTION_ID>" `
    -Location "eastus2"
```

#### 2. Rebuild Containers

```powershell
.\scripts\Deploy-Containers.ps1 `
    -ContainerRegistryName "acrrisk..." `
    -ResourceGroupName "rg-risk-demo"
```

#### 3. Redeploy Kubernetes Components

```powershell
.\scripts\Deploy-Kubernetes.ps1 `
    -AksName "aks-risk-demo" `
    -ResourceGroupName "rg-risk-demo" `
    -ContainerRegistryName "acrrisk..." `
    -KeyVaultName "kv-risk..." `
    -AiProjectEndpoint "https://..." `
    -ManagedIdentityName "id-risk-demo" `
    -ManagedIdentityClientId "..."
```

#### 4. Deploy/Update Agents Only

```powershell
.\scripts\Deploy-FoundryAgents.ps1 `
    -AiProjectEndpoint "https://..." `
    -McpContractsIP "20.1.2.3" `
    -McpRiskIP "20.1.2.4" `
    -McpMarketIP "20.1.2.5"
```

## Shared Functions

The `common/DeploymentFunctions.ps1` module provides reusable utilities:

- `Initialize-AzureContext` - Azure CLI login and subscription selection
- `Test-RequiredTools` - Validate prerequisites (kubectl, helm, etc.)
- `Get-RandomAlphaNumeric` - Generate unique resource tokens
- `New-SecurePassword` - Generate secure passwords
- `Invoke-HelmWithRetry` - Retry logic for Helm deployments
- `Get-ServiceExternalIP` - Wait for LoadBalancer IPs
- `New-FederatedIdentityCredential` - Create workload identity credentials

## Benefits of Modular Structure

1. **Faster iterations** - Rebuild only what changed
2. **Easier debugging** - Run individual phases
3. **Better testing** - Test components in isolation
4. **Reusable** - Use scripts in CI/CD pipelines
5. **Maintainable** - Clearer separation of concerns

## Migration from Original deploy.ps1

The original `deploy.ps1` remains unchanged. The new structure is in:
- `deploy-new.ps1` - New main orchestrator
- `scripts/` - Modular components

To switch to the new structure, use `deploy-new.ps1` instead of `deploy.ps1`.
