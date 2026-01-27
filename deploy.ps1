# Contract Risk MCP Platform - Main Deployment Orchestrator
# This script coordinates the full end-to-end deployment

param (
    [Parameter(Mandatory=$true)]
    [string]$Subscription,
    
    [Parameter(Mandatory=$false)]
    [string]$Location = "eastus2",
    
    [Parameter(Mandatory=$false)]
    [string]$UserObjectId,
    
    [Parameter(Mandatory=$false)]
    [string]$AILocation
)

# Import common functions
Import-Module "$PSScriptRoot\scripts\common\DeploymentFunctions.psm1" -Force

Write-Host @"

============================================================
  Contract Risk MCP Platform - Deployment Orchestrator
============================================================

"@ -ForegroundColor Cyan

# Validate prerequisites
Test-RequiredTools -Tools @("kubectl", "helm", "kubelogin")

# Initialize Azure context
Initialize-AzureContext -Subscription $Subscription

# PHASE 1: Deploy Infrastructure
Write-Host "`n=== PHASE 1: Infrastructure Deployment ===" -ForegroundColor Magenta
$infraOutputs = & "$PSScriptRoot\scripts\Deploy-Infrastructure.ps1" `
    -Subscription $Subscription `
    -Location $Location `
    -AILocation $AILocation `
    -UserObjectId $UserObjectId

# PHASE 2: Build Container Images
Write-Host "`n=== PHASE 2: Container Image Builds ===" -ForegroundColor Magenta
& "$PSScriptRoot\scripts\Deploy-Containers.ps1" `
    -ContainerRegistryName $infraOutputs.containerRegistryName `
    -ResourceGroupName $infraOutputs.resourceGroupName

# PHASE 3: Deploy Kubernetes Platform
Write-Host "`n=== PHASE 3: Kubernetes Platform Deployment ===" -ForegroundColor Magenta
$k8sOutputs = & "$PSScriptRoot\scripts\Deploy-Kubernetes.ps1" `
    -AksName $infraOutputs.aksName `
    -ResourceGroupName $infraOutputs.resourceGroupName `
    -ContainerRegistryName $infraOutputs.containerRegistryName `
    -KeyVaultName $infraOutputs.keyVaultName `
    -AiProjectEndpoint $infraOutputs.aiProjectEndpoint `
    -ManagedIdentityName $infraOutputs.managedIdentityName `
    -ManagedIdentityClientId $infraOutputs.managedIdentityClientId

# PHASE 4: Deploy Foundry Agents
if ($k8sOutputs.mcpContractsIP -and $k8sOutputs.mcpRiskIP -and $k8sOutputs.mcpMarketIP) {
    Write-Host "`n=== PHASE 4: Foundry Agents Deployment ===" -ForegroundColor Magenta
    
    try {
        & "$PSScriptRoot\scripts\Deploy-FoundryAgents.ps1" `
            -AiProjectEndpoint $infraOutputs.aiProjectEndpoint `
            -McpContractsIP $k8sOutputs.mcpContractsIP `
            -McpRiskIP $k8sOutputs.mcpRiskIP `
            -McpMarketIP $k8sOutputs.mcpMarketIP
    } catch {
        Write-Host "`n[WARNING] Agent deployment encountered issues: $_" -ForegroundColor Yellow
        Write-Host "You can deploy agents manually later:" -ForegroundColor Gray
        Write-Host "  .\scripts\Deploy-FoundryAgents.ps1 -AiProjectEndpoint <ENDPOINT> -McpContractsIP <IP> ..." -ForegroundColor Gray
    }
} else {
    Write-Host "`n[WARNING] Could not retrieve all MCP service IPs. Skipping agent deployment." -ForegroundColor Yellow
}

# Deployment Summary
Write-Host @"

============================================================
                 Deployment Summary
============================================================

"@ -ForegroundColor Cyan

Write-Host "[✓] Azure Infrastructure deployed" -ForegroundColor Green
Write-Host "[✓] Container images built and pushed to ACR" -ForegroundColor Green
Write-Host "[✓] Platform components deployed to AKS" -ForegroundColor Green
Write-Host "[✓] RabbitMQ deployed" -ForegroundColor Green
Write-Host "[✓] MCP tool servers deployed" -ForegroundColor Green
Write-Host "[✓] Risk workers deployed with KEDA autoscaling" -ForegroundColor Green

Write-Host "`n=== Service Endpoints ===" -ForegroundColor Cyan

if ($k8sOutputs.grafanaIP) {
    Write-Host "Grafana: http://$($k8sOutputs.grafanaIP):3000 (admin/admin)" -ForegroundColor Green
} else {
    Write-Host "Grafana: kubectl port-forward -n platform svc/grafana 3000:3000" -ForegroundColor Yellow
}

if ($k8sOutputs.mcpContractsIP) {
    Write-Host "MCP Contracts: http://$($k8sOutputs.mcpContractsIP)" -ForegroundColor Green
}
if ($k8sOutputs.mcpRiskIP) {
    Write-Host "MCP Risk: http://$($k8sOutputs.mcpRiskIP)" -ForegroundColor Green
}
if ($k8sOutputs.mcpMarketIP) {
    Write-Host "MCP Market: http://$($k8sOutputs.mcpMarketIP)" -ForegroundColor Green
}

Write-Host "`nRabbitMQ: kubectl port-forward -n rabbitmq svc/rabbitmq 15672:15672" -ForegroundColor Gray

Write-Host @"

============================================================
              Deployment Complete!
============================================================

"@ -ForegroundColor Green
