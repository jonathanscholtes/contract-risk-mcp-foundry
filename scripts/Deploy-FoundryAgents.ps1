# Deploy Foundry agents and restart orchestrator
# This script wraps the Python agent deployment and restarts the orchestrator

param (
    [Parameter(Mandatory=$true)]
    [string]$AiProjectEndpoint,
    
    [Parameter(Mandatory=$true)]
    [string]$McpContractsIP,
    
    [Parameter(Mandatory=$true)]
    [string]$McpRiskIP,
    
    [Parameter(Mandatory=$true)]
    [string]$McpMarketIP,
    
    [Parameter(Mandatory=$false)]
    [string]$ModelDeployment = "gpt-4o"
)

# Import common functions
Import-Module "$PSScriptRoot\common\DeploymentFunctions.ps1" -Force

Write-Host "`n=== Deploying Foundry Agents ===" -ForegroundColor Cyan

# Check Python availability
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Python not found. Cannot deploy agents." -ForegroundColor Red
    throw "Python is required for agent deployment"
}

# Install Python dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
pip install -r scripts/requirements-agents.txt --quiet

# Build MCP URLs
$mcpContractsUrl = "http://${McpContractsIP}/mcp"
$mcpRiskUrl = "http://${McpRiskIP}/mcp"
$mcpMarketUrl = "http://${McpMarketIP}/mcp"

Write-Host "`nAgent Configuration:" -ForegroundColor Cyan
Write-Host "  Project Endpoint: $AiProjectEndpoint" -ForegroundColor White
Write-Host "  Model Deployment: $ModelDeployment" -ForegroundColor White
Write-Host "  MCP Contracts URL: $mcpContractsUrl" -ForegroundColor White
Write-Host "  MCP Risk URL: $mcpRiskUrl" -ForegroundColor White
Write-Host "  MCP Market URL: $mcpMarketUrl" -ForegroundColor White

# Verify MCP services are running
Write-Host "`nVerifying MCP services are running..." -ForegroundColor Yellow
$mcpServices = @("mcp-contracts", "mcp-risk", "mcp-market")
$allReady = $true

foreach ($svc in $mcpServices) {
    $podStatus = kubectl get pods -n tools -l app=$svc -o jsonpath='{.items[0].status.phase}' 2>$null
    if ($podStatus -eq "Running") {
        Write-Host "  $svc is running" -ForegroundColor Green
    } else {
        Write-Host "  $svc is not ready (status: $podStatus)" -ForegroundColor Yellow
        $allReady = $false
    }
}

if (-not $allReady) {
    throw "MCP services not ready"
}

# Deploy agents
Write-Host "`nDeploying autonomous agents to Microsoft Foundry..." -ForegroundColor Yellow

python scripts/deploy_foundry_agents.py `
    --project-endpoint $AiProjectEndpoint `
    --model-deployment $ModelDeployment `
    --mcp-contracts-url $mcpContractsUrl `
    --mcp-risk-url $mcpRiskUrl `
    --mcp-market-url $mcpMarketUrl

if ($LASTEXITCODE -ne 0) {
    throw "Agent deployment failed"
}

Write-Host "`n[OK] Foundry agents deployed successfully" -ForegroundColor Green

# Restart orchestrator
Write-Host "`nRestarting agent orchestrator to connect to deployed agents..." -ForegroundColor Yellow
kubectl rollout restart deployment agent-orchestrator -n tools
kubectl rollout status deployment agent-orchestrator -n tools --timeout=2m

Write-Host "[OK] Orchestrator restarted successfully" -ForegroundColor Green
