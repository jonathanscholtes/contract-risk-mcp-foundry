# Deploy Azure Infrastructure using Bicep
# This script deploys all Azure resources (AI Foundry, AKS, ACR, Key Vault, etc.)

param (
    [Parameter(Mandatory=$true)]
    [string]$Subscription,
    
    [Parameter(Mandatory=$false)]
    [string]$Location = "eastus2",
    
    [Parameter(Mandatory=$false)]
    [string]$AILocation,
    
    [Parameter(Mandatory=$false)]
    [string]$UserObjectId,
    
    [Parameter(Mandatory=$false)]
    [string]$ProjectName = "risk",
    
    [Parameter(Mandatory=$false)]
    [string]$EnvironmentName = "demo",
    
    [Parameter(Mandatory=$false)]
    [string]$ResourceToken
)

# Import common functions
Import-Module "$PSScriptRoot\common\DeploymentFunctions.psm1" -Force

# Default AI location to primary location if not specified
if (-not $AILocation) {
    $AILocation = $Location
}

Write-Host "`n=== Deploying Azure Infrastructure ===" -ForegroundColor Cyan
Write-Host "Subscription: $Subscription" -ForegroundColor White
Write-Host "Location: $Location" -ForegroundColor White
Write-Host "AI Location: $AILocation" -ForegroundColor White

# Generate resource token if not provided
if (-not $ResourceToken) {
    $timestamp = Get-Date -Format "yyyyMMddHHmmss"
    $ResourceToken = Get-RandomAlphaNumeric -Length 12 -Seed $timestamp
    Write-Host "Generated Resource Token: $ResourceToken" -ForegroundColor Cyan
}

# Generate MongoDB admin password
$mongoAdminPassword = New-SecurePassword -Length 16
Write-Host "Generated MongoDB admin password (Length: $($mongoAdminPassword.Length))" -ForegroundColor Yellow

# Deploy Bicep template
$deploymentName = "deployment-$ProjectName-$ResourceToken"
$templateFile = "infra/main.bicep"

Write-Host "`nDeploying Bicep template..." -ForegroundColor Yellow
$deploymentOutput = az deployment sub create `
    --name $deploymentName `
    --location $Location `
    --template-file $templateFile `
    --parameters `
        environmentName=$EnvironmentName `
        projectName=$ProjectName `
        resourceToken=$ResourceToken `
        location=$Location `
        AIlocation=$AILocation `
        userObjectId=$UserObjectId `
        mongoAdminPassword=$mongoAdminPassword `
    --query "properties.outputs"

# Parse and return deployment outputs
$outputs = $deploymentOutput | ConvertFrom-Json

Write-Host "`n[OK] Infrastructure deployed successfully" -ForegroundColor Green
Write-Host "`nDeployment Outputs:" -ForegroundColor Cyan
Write-Host "  Resource Group: $($outputs.resourceGroupName.value)" -ForegroundColor White
Write-Host "  AKS Cluster: $($outputs.aksName.value)" -ForegroundColor White
Write-Host "  Container Registry: $($outputs.containerRegistryName.value)" -ForegroundColor White
Write-Host "  AI Project Endpoint: $($outputs.aiProjectEndpoint.value)" -ForegroundColor White

# Return outputs as object
return [PSCustomObject]@{
    managedIdentityName = $outputs.managedIdentityName.value
    managedIdentityClientId = $outputs.managedIdentityClientId.value
    resourceGroupName = $outputs.resourceGroupName.value
    storageAccountName = $outputs.storageAccountName.value
    keyVaultName = $outputs.keyVaultName.value
    aiProjectEndpoint = $outputs.aiProjectEndpoint.value
    containerRegistryName = $outputs.containerRegistryName.value
    aksName = $outputs.aksName.value
}
