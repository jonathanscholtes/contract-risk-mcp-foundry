param (
    [string]$Subscription,
    [string]$Location = "eastus2",
    [string]$AILocation
)

# If $AILocation is not provided, default it to $Location
if (-not $AILocation) {
    $AILocation = $Location
}


Write-Host "Subscription: $Subscription"
Write-Host "Location: $Location"
Write-Host "AI Location: $AILocation"


# Variables
$projectName = "contract-risk"
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


$deploymentNameInfra = "deployment-transport-$resourceToken"
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
$searchServicename = $deploymentOutputJsonInfra.searchServicename.value
$containerRegistryName = $deploymentOutputJsonInfra.containerRegistryName.value


Write-Host "=== Building Images for Containers ==="
Write-Host "Using ACR: $containerRegistryName"
Write-Host "Resource Group: $resourceGroupName`n"

# Define image names and paths for Contract Risk Platform
$images = @(
    @{ name = "agent-orchestrator"; path = ".\apps\agent-orchestrator"; dockerfile = ".\apps\agent-orchestrator\Dockerfile" }
    @{ name = "mcp-contracts"; path = "."; dockerfile = ".\apps\mcp-contracts\Dockerfile" }
    @{ name = "mcp-risk"; path = "."; dockerfile = ".\apps\mcp-risk\Dockerfile" }
    @{ name = "mcp-market"; path = "."; dockerfile = ".\apps\mcp-market\Dockerfile" }
    @{ name = "risk-worker"; path = "."; dockerfile = ".\apps\risk-worker\Dockerfile" }
)

# Build images
foreach ($image in $images) {
    Write-Host "Building image '$($image.name):latest'..."
    Write-Host "az acr build --resource-group $resourceGroupName --registry $containerRegistryName --file $($image.dockerfile) --image $($image.name):latest $($image.path)"

    az acr build `
        --resource-group $resourceGroupName `
        --registry $containerRegistryName `
        --file $image.dockerfile `
        --image "$($image.name):latest" `
        $image.path
}

Write-Host "`n=== Deploying Platform Components with Helm ==="

# Set ACR name for Helm values
$acrLoginServer = "$containerRegistryName.azurecr.io"

# Get AKS credentials (assuming AKS cluster exists from Bicep deployment)
$aksName = $deploymentOutputJsonInfra.aksName.value
Write-Host "Getting AKS credentials for cluster: $aksName"
az aks get-credentials --resource-group $resourceGroupName --name $aksName --overwrite-existing

# Deploy Helm charts
Write-Host "`n1. Deploying Platform (Monitoring)..."
helm upgrade --install platform .\k8s\helm\platform `
    --namespace platform --create-namespace `
    --wait

Write-Host "`n2. Deploying RabbitMQ..."
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm upgrade --install rabbitmq bitnami/rabbitmq `
    --namespace rabbitmq --create-namespace `
    --set auth.username=user `
    --set auth.password=password `
    --set metrics.enabled=true `
    --set metrics.serviceMonitor.enabled=true `
    --wait

Write-Host "`n3. Deploying MCP Tools..."
helm upgrade --install mcp-tools .\k8s\helm\mcp-tools `
    --namespace tools --create-namespace `
    --set registry=$acrLoginServer `
    --set foundryAgent.endpoint=$aiAccountEndpoint `
    --set foundryAgent.apiKey="PLACEHOLDER-UPDATE-IN-K8S-SECRET" `
    --wait

Write-Host "`n4. Deploying Risk Workers..."
helm upgrade --install risk-workers .\k8s\helm\risk-workers `
    --namespace workers --create-namespace `
    --set registry=$acrLoginServer `
    --wait

Write-Host "`n=== Deployment Summary ==="
Write-Host "✅ Azure Infrastructure deployed"
Write-Host "✅ Container images built and pushed to ACR"
Write-Host "✅ Platform components deployed to AKS"
Write-Host "✅ RabbitMQ deployed"
Write-Host "✅ MCP tool servers deployed"
Write-Host "✅ Risk workers deployed with KEDA autoscaling"

Write-Host "`n=== Next Steps ==="
Write-Host "1. Update Foundry agent API key:"
Write-Host "   kubectl edit secret foundry-agent-secret -n tools"
Write-Host ""
Write-Host "2. Access services:"
Write-Host "   Grafana:  kubectl port-forward -n platform svc/grafana 3000:3000"
Write-Host "   RabbitMQ: kubectl port-forward -n rabbitmq svc/rabbitmq 15672:15672"
Write-Host ""
Write-Host "3. Seed sample data:"
Write-Host "   python scripts\seed_contracts.py"
Write-Host ""
Write-Host "4. Run EURUSD shock demo:"
Write-Host "   python scripts\demo_eurusd_shock.py"
