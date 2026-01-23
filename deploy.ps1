param (
    [string]$Subscription,
    [string]$Location = "eastus2",
    [string]$AILocation,
    [string]$UserObjectId
)

# Set UTF-8 encoding for proper Unicode character display
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# If $AILocation is not provided, default it to $Location
if (-not $AILocation) {
    $AILocation = $Location
}


Write-Host "Subscription: $Subscription" -ForegroundColor Cyan
Write-Host "Location: $Location" -ForegroundColor Cyan
Write-Host "AI Location: $AILocation" -ForegroundColor Cyan


# Variables
$projectName = "risk"
$environmentName = "demo"
$timestamp = Get-Date -Format "yyyyMMddHHmmss"

function Get-RandomAlphaNumeric {
    param (
        [int]$Length = 12,
        [string]$Seed
    )

    $base62Chars = "abcdefghijklmnopqrstuvwxyz123456789"

    # Convert the seed string to a hash (e.g., MD5)
    $md5 = [System.Security.Cryptography.MD5]::Create()
    $seedBytes = [System.Text.Encoding]::UTF8.GetBytes($Seed)
    $hashBytes = $md5.ComputeHash($seedBytes)

    # Use bytes from hash to generate characters
    $randomString = ""
    for ($i = 0; $i -lt $Length; $i++) {
        $index = $hashBytes[$i % $hashBytes.Length] % $base62Chars.Length
        $randomString += $base62Chars[$index]
    }

    return $randomString
}

# Example usage: Generate a resource token based on a seed
$resourceToken = Get-RandomAlphaNumeric -Length 12 -Seed $timestamp

# Clear account context and configure Azure CLI settings
az account clear
az config set core.enable_broker_on_windows=false
az config set core.login_experience_v2=off

# Login to Azure
az login 
az account set --subscription $Subscription

# Check for required tools
Write-Host "`n=== Checking Required Tools ===" -ForegroundColor Cyan

$missingTools = @()

# Check for kubectl
try {
    $null = kubectl version --client --short 2>$null
    Write-Host "kubectl found" -ForegroundColor Green
} catch {
    Write-Host "kubectl not found" -ForegroundColor Red
    $missingTools += "kubectl"
}

# Check for helm
try {
    $null = helm version --short 2>$null
    Write-Host "helm found" -ForegroundColor Green
} catch {
    Write-Host "helm not found" -ForegroundColor Red
    $missingTools += "helm"
}

# Check for kubelogin
try {
    $null = kubelogin --version 2>$null
    Write-Host "kubelogin found" -ForegroundColor Green
} catch {
    Write-Host "kubelogin not found" -ForegroundColor Red
    $missingTools += "kubelogin"
}

if ($missingTools.Count -gt 0) {
    Write-Host "`n❌ Missing required tools: $($missingTools -join ', ')" -ForegroundColor Red
    Write-Host "`nInstallation instructions:" -ForegroundColor Yellow
    
    if ($missingTools -contains "kubectl") {
        Write-Host "`nkubectl:" -ForegroundColor White
        Write-Host "  az aks install-cli" -ForegroundColor Gray
        Write-Host "  Or download from: https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/" -ForegroundColor Gray
    }
    
    if ($missingTools -contains "helm") {
        Write-Host "`nhelm:" -ForegroundColor White
        Write-Host "  winget install Helm.Helm" -ForegroundColor Gray
        Write-Host "  Or via Chocolatey: choco install kubernetes-helm" -ForegroundColor Gray
        Write-Host "  Or download from: https://github.com/helm/helm/releases" -ForegroundColor Gray
    }

    if ($missingTools -contains "kubelogin") {
        Write-Host "`nkubelogin (Azure Kubernetes Authentication):" -ForegroundColor White
        Write-Host "  az aks install-cli" -ForegroundColor Gray
        Write-Host "  Or download from: https://github.com/Azure/kubelogin/releases" -ForegroundColor Gray
    }
    
    Write-Host "`nAfter installation, restart your PowerShell session and run the script again." -ForegroundColor Yellow
    exit 1
}

Write-Host "All required tools found`n" -ForegroundColor Green


$deploymentNameInfra = "deployment-risk-$resourceToken"
$templateFile = "infra/main.bicep"

$deploymentOutput = az deployment sub create `
    --name $deploymentNameInfra `
    --location $Location `
    --template-file $templateFile `
    --parameters `
        environmentName=$environmentName `
        projectName=$projectName `
        resourceToken=$resourceToken `
        location=$Location `
        AIlocation=$AILocation `
        userObjectId=$UserObjectId `
    --query "properties.outputs"

# Parse deployment outputs
$deploymentOutputJsonInfra = $deploymentOutput | ConvertFrom-Json
$managedIdentityName = $deploymentOutputJsonInfra.managedIdentityName.value
#$appServicePlanName = $deploymentOutputJsonInfra.appServicePlanName.value
$resourceGroupName = $deploymentOutputJsonInfra.resourceGroupName.value
$storageAccountName = $deploymentOutputJsonInfra.storageAccountName.value
$logAnalyticsWorkspaceName = $deploymentOutputJsonInfra.logAnalyticsWorkspaceName.value
$applicationInsightsName = $deploymentOutputJsonInfra.applicationInsightsName.value
$keyVaultName = $deploymentOutputJsonInfra.keyVaultName.value
$OpenAIEndPoint = $deploymentOutputJsonInfra.OpenAIEndPoint.value
$aiAccountEndpoint = $deploymentOutputJsonInfra.aiAccountEndpoint.value
$cosmosdbEndpoint = $deploymentOutputJsonInfra.cosmosdbEndpoint.value
#$searchServicename = $deploymentOutputJsonInfra.searchServicename.value
$containerRegistryName = $deploymentOutputJsonInfra.containerRegistryName.value
$aksName = $deploymentOutputJsonInfra.aksName.value

Write-Host "=== Building Images for Containers ===" -ForegroundColor Cyan
Write-Host "Using ACR: $containerRegistryName" -ForegroundColor White
Write-Host "Resource Group: $resourceGroupName`n" -ForegroundColor White

# Define image names and paths for Contract Risk Platform
$images = @(
    @{ name = "agent-orchestrator"; path = "."; dockerfile = ".\apps\agent-orchestrator\Dockerfile" }
    @{ name = "mcp-contracts"; path = "."; dockerfile = ".\apps\mcp-contracts\Dockerfile" }
    @{ name = "mcp-risk"; path = "."; dockerfile = ".\apps\mcp-risk\Dockerfile" }
    @{ name = "mcp-market"; path = "."; dockerfile = ".\apps\mcp-market\Dockerfile" }
    @{ name = "risk-worker"; path = "."; dockerfile = ".\apps\risk-worker\Dockerfile" }
)


# Build images
foreach ($image in $images) {

    Write-Host "Building image '$($image.name):latest' from '$($image.path)'..." -ForegroundColor Yellow

    az acr build `
        --resource-group $resourceGroupName `
        --registry $containerRegistryName `
        --file $image.dockerfile `
        --image "$($image.name):latest" `
        $image.path

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to build image '$($image.name)'" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Image '$($image.name):latest' built successfully" -ForegroundColor Green
}

Write-Host "`n=== Deploying Platform Components with Helm ===" -ForegroundColor Cyan

# Set ACR name for Helm values
$acrLoginServer = "$containerRegistryName.azurecr.io"



Write-Host "Getting AKS credentials for cluster: $aksName" -ForegroundColor Yellow
az aks get-credentials --resource-group $resourceGroupName --name $aksName --overwrite-existing

# Convert kubeconfig to use Azure CLI credentials (no additional login required)
Write-Host "Configuring kubectl to use Azure CLI authentication..." -ForegroundColor Yellow
kubelogin convert-kubeconfig -l azurecli

# Deploy Helm charts
Write-Host "`n1. Deploying Platform (Monitoring)..." -ForegroundColor Magenta
helm upgrade --install platform .\k8s\helm\platform `
    --namespace platform --create-namespace `
    --wait

Write-Host "`n2. Deploying RabbitMQ..." -ForegroundColor Magenta
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm upgrade --install rabbitmq bitnami/rabbitmq `
    --namespace rabbitmq --create-namespace `
    --set auth.username=user `
    --set auth.password=password `
    --set metrics.enabled=true `
    --set metrics.serviceMonitor.enabled=true `
    --wait

Write-Host "`n3. Deploying MCP Tools..." -ForegroundColor Magenta
helm upgrade --install mcp-tools .\k8s\helm\mcp-tools `
    --namespace tools --create-namespace `
    --set registry=$acrLoginServer `
    --set foundryAgent.endpoint=$aiAccountEndpoint `
    --set foundryAgent.apiKey="PLACEHOLDER-UPDATE-IN-K8S-SECRET" `
    --wait

Write-Host "`n4. Deploying Risk Workers..." -ForegroundColor Magenta
helm upgrade --install risk-workers .\k8s\helm\risk-workers `
    --namespace workers --create-namespace `
    --set registry=$acrLoginServer `
    --wait

Write-Host "`n=== Deployment Summary ===" -ForegroundColor Cyan
Write-Host "✅ Azure Infrastructure deployed" -ForegroundColor Green
Write-Host "✅ Container images built and pushed to ACR" -ForegroundColor Green
Write-Host "✅ Platform components deployed to AKS" -ForegroundColor Green
Write-Host "✅ RabbitMQ deployed" -ForegroundColor Green
Write-Host "✅ MCP tool servers deployed" -ForegroundColor Green
Write-Host "✅ Risk workers deployed with KEDA autoscaling" -ForegroundColor Green

Write-Host "`n=== Next Steps ===" -ForegroundColor Cyan
Write-Host "1. Update Foundry agent API key:" -ForegroundColor Yellow
Write-Host "   kubectl edit secret foundry-agent-secret -n tools" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Access services:" -ForegroundColor Yellow
Write-Host "   Grafana:  kubectl port-forward -n platform svc/grafana 3000:3000" -ForegroundColor Gray
Write-Host "   RabbitMQ: kubectl port-forward -n rabbitmq svc/rabbitmq 15672:15672" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Seed sample data:" -ForegroundColor Yellow
Write-Host "   python scripts/seed_contracts.py" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Run EURUSD shock demo:" -ForegroundColor Yellow
Write-Host "   python scripts/demo_eurusd_shock.py" -ForegroundColor Gray
