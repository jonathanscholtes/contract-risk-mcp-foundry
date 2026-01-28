# Build and push container images to Azure Container Registry
# This script builds all application containers

param (
    [Parameter(Mandatory=$true)]
    [string]$ContainerRegistryName,
    
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroupName,
    
    [Parameter(Mandatory=$false)]
    [string[]]$Images = @("agent-orchestrator", "mcp-contracts", "mcp-risk", "mcp-market", "risk-worker")
)

Write-Host "`n=== Building Container Images ===" -ForegroundColor Cyan
Write-Host "Container Registry: $ContainerRegistryName" -ForegroundColor White
Write-Host "Resource Group: $ResourceGroupName" -ForegroundColor White

# Define image configurations
$imageConfigs = @{
    "agent-orchestrator" = @{ path = "."; dockerfile = ".\apps\agent-orchestrator\Dockerfile" }
    "mcp-contracts" = @{ path = "."; dockerfile = ".\apps\mcp-contracts\Dockerfile" }
    "mcp-risk" = @{ path = "."; dockerfile = ".\apps\mcp-risk\Dockerfile" }
    "mcp-market" = @{ path = "."; dockerfile = ".\apps\mcp-market\Dockerfile" }
    "risk-worker" = @{ path = "."; dockerfile = ".\apps\risk-worker\Dockerfile" }
}

# Build each image
foreach ($imageName in $Images) {
    if (-not $imageConfigs.ContainsKey($imageName)) {
        Write-Host "Unknown image: $imageName, skipping..." -ForegroundColor Yellow
        continue
    }
    
    $config = $imageConfigs[$imageName]
    
    Write-Host "`nBuilding image '${imageName}:latest'..." -ForegroundColor Yellow
    
    az acr build `
        --resource-group $ResourceGroupName `
        --registry $ContainerRegistryName `
        --file $config.dockerfile `
        --image "${imageName}:latest" `
        $config.path
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to build image '$imageName'" -ForegroundColor Red
        throw "Image build failed"
    }
    
    Write-Host "Image '${imageName}:latest' built successfully" -ForegroundColor Green
}

Write-Host "`n[OK] All container images built successfully" -ForegroundColor Green
