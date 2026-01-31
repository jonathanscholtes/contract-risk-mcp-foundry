# Deploy platform components to AKS using Helm
# This script deploys monitoring, RabbitMQ, MCP tools, and risk workers

param (
    [Parameter(Mandatory=$true)]
    [string]$AksName,
    
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroupName,
    
    [Parameter(Mandatory=$true)]
    [string]$ContainerRegistryName,
    
    [Parameter(Mandatory=$true)]
    [string]$KeyVaultName,
    
    [Parameter(Mandatory=$true)]
    [string]$AiProjectEndpoint,
    
    [Parameter(Mandatory=$true)]
    [string]$ManagedIdentityName,
    
    [Parameter(Mandatory=$true)]
    [string]$ManagedIdentityClientId
)

# Import common functions
Import-Module "$PSScriptRoot\common\DeploymentFunctions.psm1" -Force

Write-Host "`n=== Deploying Platform Components to AKS ===" -ForegroundColor Cyan

# Get AKS credentials
Write-Host "Getting AKS credentials for cluster: $AksName" -ForegroundColor Yellow
az aks get-credentials --resource-group $ResourceGroupName --name $AksName --overwrite-existing
kubelogin convert-kubeconfig -l azurecli

# Fix Docker credential helper issue
$dockerConfigPath = "$env:USERPROFILE\.docker\config.json"
if (Test-Path $dockerConfigPath) {
    Remove-Item $dockerConfigPath -Force
}

# Get configuration values
$tenantId = az account show --query tenantId -o tsv
$oidcIssuer = az aks show --name $AksName --resource-group $ResourceGroupName --query "oidcIssuerProfile.issuerUrl" -o tsv
$acrLoginServer = "$ContainerRegistryName.azurecr.io"

# Retrieve RabbitMQ credentials
Write-Host "`nRetrieving RabbitMQ credentials from Key Vault..." -ForegroundColor Yellow
$rabbitmqUsername = az keyvault secret show --vault-name $KeyVaultName --name "rabbitmq-username" --query value -o tsv
$rabbitmqPassword = az keyvault secret show --vault-name $KeyVaultName --name "rabbitmq-password" --query value -o tsv

# 1. Deploy Platform (Monitoring)
Write-Host "`n1. Deploying Platform (Monitoring)..." -ForegroundColor Magenta
helm upgrade --install platform .\k8s\helm\platform `
    --namespace platform --create-namespace `
    --wait --timeout 10m
if ($LASTEXITCODE -ne 0) { throw "Platform deployment failed" }
Write-Host "[OK] Platform deployed successfully" -ForegroundColor Green

# 2. Deploy RabbitMQ
Write-Host "`n2. Deploying RabbitMQ..." -ForegroundColor Magenta
Write-Host "Adding Bitnami Helm repository..." -ForegroundColor Gray
helm repo add bitnami https://charts.bitnami.com/bitnami 2>$null
Write-Host "Updating Helm repositories..." -ForegroundColor Gray
helm repo update

Write-Host "Deploying RabbitMQ Helm chart (this may take several minutes)..." -ForegroundColor Yellow
$env:HELM_DEBUG="0"
helm upgrade --install rabbitmq bitnami/rabbitmq `
    --namespace rabbitmq --create-namespace `
    --values .\k8s\helm\rabbitmq-values.yaml `
    --set auth.username=$rabbitmqUsername `
    --set auth.password=$rabbitmqPassword `
    --wait --timeout 20m 

if ($LASTEXITCODE -ne 0) { 
    Write-Host "[WARNING] RabbitMQ deployment timed out waiting for ready state" -ForegroundColor Yellow
    Write-Host "Checking RabbitMQ pod status..." -ForegroundColor Gray
    kubectl get pods -n rabbitmq 
    Write-Host "Note: RabbitMQ may still be initializing. Check status with: kubectl get pods -n rabbitmq" -ForegroundColor Gray
} else {
    Write-Host "[OK] RabbitMQ deployed successfully" -ForegroundColor Green
}

# 3. Configure Workload Identity
Write-Host "`n3. Configuring Azure Workload Identity..." -ForegroundColor Magenta

New-FederatedIdentityCredential `
    -ServiceAccountName "agent-orchestrator-sa" `
    -ManagedIdentityName $ManagedIdentityName `
    -ResourceGroupName $ResourceGroupName `
    -OidcIssuer $oidcIssuer

New-FederatedIdentityCredential `
    -ServiceAccountName "mcp-contracts-sa" `
    -ManagedIdentityName $ManagedIdentityName `
    -ResourceGroupName $ResourceGroupName `
    -OidcIssuer $oidcIssuer

New-FederatedIdentityCredential `
    -ServiceAccountName "mcp-market-sa" `
    -ManagedIdentityName $ManagedIdentityName `
    -ResourceGroupName $ResourceGroupName `
    -OidcIssuer $oidcIssuer

New-FederatedIdentityCredential `
    -ServiceAccountName "mcp-risk-sa" `
    -ManagedIdentityName $ManagedIdentityName `
    -ResourceGroupName $ResourceGroupName `
    -OidcIssuer $oidcIssuer

New-FederatedIdentityCredential `
    -ServiceAccountName "risk-worker-sa" `
    -Namespace "workers" `
    -ManagedIdentityName $ManagedIdentityName `
    -ResourceGroupName $ResourceGroupName `
    -OidcIssuer $oidcIssuer

# 4. Deploy MCP Tools
Write-Host "`n4. Deploying MCP Tools..." -ForegroundColor Magenta
Write-Host "Deploying MCP tool servers (this may take several minutes)..." -ForegroundColor Yellow
helm upgrade --install mcp-tools .\k8s\helm\mcp-tools `
    --namespace tools --create-namespace `
    --set registry=$acrLoginServer `
    --set agentOrchestrator.tag=latest `
    --set mcpContracts.tag=latest `
    --set mcpRisk.tag=latest `
    --set mcpMarket.tag=latest `
    --set azureAiProject.endpoint=$AiProjectEndpoint `
    --set azureAiProject.managedIdentityClientId=$ManagedIdentityClientId `
    --set keyVault.name=$KeyVaultName `
    --set keyVault.tenantId=$tenantId `
    --set rabbitmq.user=$rabbitmqUsername `
    --set rabbitmq.password=$rabbitmqPassword `
    --wait --timeout 20m 

if ($LASTEXITCODE -ne 0) { 
    Write-Host "`n[WARNING] MCP Tools deployment timed out waiting for ready state. Checking pod status..." -ForegroundColor Yellow
    Write-Host "`nPod Status:" -ForegroundColor Yellow
    kubectl get pods -n tools 
    Write-Host "`nNote: Pods may still be initializing. Monitor with: kubectl get pods -n tools -w" -ForegroundColor Gray
} else {
    Write-Host "[OK] MCP Tools deployed successfully" -ForegroundColor Green
}

# 5. Deploy Risk Workers
Write-Host "`n5. Deploying Risk Workers..." -ForegroundColor Magenta
Write-Host "Deploying risk workers with KEDA autoscaling (this may take several minutes)..." -ForegroundColor Yellow
helm upgrade --install risk-workers .\k8s\helm\risk-workers `
    --namespace workers --create-namespace `
    --set registry=$acrLoginServer `
    --set riskWorker.tag=latest `
    --set azureAiProject.managedIdentityClientId=$ManagedIdentityClientId `
    --set keyVault.name=$KeyVaultName `
    --set keyVault.tenantId=$tenantId `
    --set rabbitmq.user=$rabbitmqUsername `
    --set rabbitmq.password=$rabbitmqPassword `
    --wait --timeout 20m 

if ($LASTEXITCODE -ne 0) { 
    Write-Host "[WARNING] Risk Workers deployment timed out waiting for ready state" -ForegroundColor Yellow
    Write-Host "Checking Risk Workers pod status..." -ForegroundColor Gray
    kubectl get pods -n workers 
    Write-Host "Note: Workers may still be initializing. Monitor with: kubectl get pods -n workers -w" -ForegroundColor Gray
} else {
    Write-Host "[OK] Risk Workers deployed successfully" -ForegroundColor Green
}

# Get service IPs
Write-Host "`nRetrieving MCP service public IPs..." -ForegroundColor Yellow

$mcpContractsIP = Get-ServiceExternalIP -ServiceName "mcp-contracts" -MaxWaitSeconds 300
$mcpRiskIP = Get-ServiceExternalIP -ServiceName "mcp-risk" -MaxWaitSeconds 300
$mcpMarketIP = Get-ServiceExternalIP -ServiceName "mcp-market" -MaxWaitSeconds 300
$grafanaIP = Get-ServiceExternalIP -ServiceName "grafana" -Namespace "platform" -MaxWaitSeconds 300

if (-not $mcpContractsIP) {
    Write-Host "[WARNING] mcp-contracts IP not assigned yet" -ForegroundColor Yellow
}
if (-not $mcpRiskIP) {
    Write-Host "[WARNING] mcp-risk IP not assigned yet" -ForegroundColor Yellow
}
if (-not $mcpMarketIP) {
    Write-Host "[WARNING] mcp-market IP not assigned yet" -ForegroundColor Yellow
}

Write-Host "`n[DEBUG] Service IPs to be returned:" -ForegroundColor Cyan
Write-Host "  mcpContractsIP: '$mcpContractsIP'" -ForegroundColor Gray
Write-Host "  mcpRiskIP: '$mcpRiskIP'" -ForegroundColor Gray
Write-Host "  mcpMarketIP: '$mcpMarketIP'" -ForegroundColor Gray
Write-Host "  grafanaIP: '$grafanaIP'" -ForegroundColor Gray

Write-Host "`n[OK] Platform components deployed successfully" -ForegroundColor Green

# Return service endpoints
return [PSCustomObject]@{
    mcpContractsIP = $mcpContractsIP
    mcpRiskIP = $mcpRiskIP
    mcpMarketIP = $mcpMarketIP
    grafanaIP = $grafanaIP
}
