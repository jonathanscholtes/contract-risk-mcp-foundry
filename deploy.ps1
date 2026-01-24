param (
    [string]$Subscription,
    [string]$Location = "eastus2",
    [string]$UserObjectId,
    [string]$AILocation
)

# Set UTF-8 encoding for proper Unicode character display
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# If $AILocation is not provided, default it to $Location
if (-not $AILocation) {
    $AILocation = $Location
}

if (-not $UserObjectId) {
    Write-Host "User Object ID not provided. Key Vault access role will not be assigned to the deploying user." -ForegroundColor Yellow
    $UserObjectId = ""
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
    Write-Host "`n[X] Missing required tools: $($missingTools -join ', ')" -ForegroundColor Red
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

# # Check if user role was assigned
# if ($deploymentOutputJsonInfra.PSObject.Properties.Name -contains 'userRoleAssigned') {
#     $userRoleAssigned = $deploymentOutputJsonInfra.userRoleAssigned.value
#     $userObjectIdReceived = $deploymentOutputJsonInfra.userObjectIdReceived.value
    
#     Write-Host "`nKey Vault RBAC Status:" -ForegroundColor Cyan
#     Write-Host "  User Role Assigned: $userRoleAssigned" -ForegroundColor $(if($userRoleAssigned -eq $true){"Green"}else{"Yellow"})
#     Write-Host "  User Object ID: $userObjectIdReceived" -ForegroundColor Gray
    
#     if ($userRoleAssigned -eq $false -and ![string]::IsNullOrEmpty($UserObjectId)) {
#         Write-Host "`n  Manually assigning Key Vault Secrets User role..." -ForegroundColor Yellow
#         az role assignment create `
#             --role "Key Vault Secrets User" `
#             --assignee-object-id $UserObjectId `
#             --assignee-principal-type User `
#             --scope "/subscriptions/$Subscription/resourceGroups/$resourceGroupName/providers/Microsoft.KeyVault/vaults/$keyVaultName"
#     }
# }

# # Wait for RBAC role assignments to propagate
# Write-Host "`nWaiting for Key Vault role assignments to propagate..." -ForegroundColor Yellow
# Write-Host "This typically takes 1-2 minutes..." -ForegroundColor Gray
# Start-Sleep -Seconds 120

# Retrieve RabbitMQ credentials from Key Vault
Write-Host "`nRetrieving RabbitMQ credentials from Key Vault..." -ForegroundColor Yellow
$rabbitmqUsername = az keyvault secret show --vault-name $keyVaultName --name "rabbitmq-username" --query value -o tsv
$rabbitmqPassword = az keyvault secret show --vault-name $keyVaultName --name "rabbitmq-password" --query value -o tsv

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

# Fix Docker credential helper issue for Helm (when Docker not installed)
$dockerConfigPath = "$env:USERPROFILE\.docker\config.json"
$dockerConfigDir = "$env:USERPROFILE\.docker"

if (Test-Path $dockerConfigPath) {
    Write-Host "Removing Docker credential helper configuration..." -ForegroundColor Yellow
    Remove-Item $dockerConfigPath -Force
    Write-Host "Docker config removed for Helm compatibility" -ForegroundColor Green
} elseif (Test-Path $dockerConfigDir) {
    # Directory exists but no config - create empty one
    Write-Host "Creating minimal Docker config for Helm..." -ForegroundColor Yellow
    '{}' | Set-Content $dockerConfigPath -Encoding utf8
}

# Function to retry Helm commands on network failures
function Invoke-HelmWithRetry {
    param (
        [string]$CommandDescription,
        [scriptblock]$Command,
        [int]$MaxRetries = 3,
        [int]$DelaySeconds = 10
    )
    
    for ($i = 1; $i -le $MaxRetries; $i++) {
        try {
            Write-Host "Attempt $i of $MaxRetries..." -ForegroundColor Gray
            & $Command
            if ($LASTEXITCODE -eq 0) {
                return $true
            }
        }
        catch {
            Write-Host "Error: $_" -ForegroundColor Yellow
        }
        
        if ($i -lt $MaxRetries) {
            Write-Host "Retrying in $DelaySeconds seconds..." -ForegroundColor Yellow
            Start-Sleep -Seconds $DelaySeconds
        }
    }
    
    Write-Host "Failed after $MaxRetries attempts" -ForegroundColor Red
    return $false
}

# Deploy Helm charts
Write-Host "`n1. Deploying Platform (Monitoring)..." -ForegroundColor Magenta
helm upgrade --install platform .\k8s\helm\platform `
    --namespace platform --create-namespace `
    --wait --timeout 10m

Write-Host "`n2. Deploying RabbitMQ..." -ForegroundColor Magenta
helm repo add bitnami https://charts.bitnami.com/bitnami 2>$null
helm repo update

$success = Invoke-HelmWithRetry -CommandDescription "Deploy RabbitMQ" -Command {
    helm upgrade --install rabbitmq bitnami/rabbitmq `
        --namespace rabbitmq --create-namespace `
        --values .\k8s\helm\rabbitmq-values.yaml `
        --set auth.username=$rabbitmqUsername `
        --set auth.password=$rabbitmqPassword `
        --wait --timeout 10m
}

if (-not $success) {
    Write-Host "RabbitMQ deployment failed. Exiting." -ForegroundColor Red
    exit 1
}

Write-Host "`n3. Deploying MCP Tools..." -ForegroundColor Magenta
helm upgrade --install mcp-tools .\k8s\helm\mcp-tools `
    --namespace tools --create-namespace `
    --set registry=$acrLoginServer `
    --set agentOrchestrator.tag=latest `
    --set mcpContracts.tag=latest `
    --set mcpRisk.tag=latest `
    --set mcpMarket.tag=latest `
    --set foundryAgent.endpoint=$aiAccountEndpoint `
    --set foundryAgent.apiKey="PLACEHOLDER-UPDATE-IN-K8S-SECRET" `
    --wait --timeout 10m

Write-Host "`nWaiting for LoadBalancer public IPs to be assigned..." -ForegroundColor Yellow
Write-Host "This may take 2-3 minutes..." -ForegroundColor Gray
Start-Sleep -Seconds 30

# Function to get external IP for a service
function Get-ServiceExternalIP {
    param (
        [string]$ServiceName,
        [string]$Namespace = "tools",
        [int]$MaxWaitSeconds = 180
    )
    
    $waited = 0
    while ($waited -lt $MaxWaitSeconds) {
        $externalIP = kubectl get svc $ServiceName -n $Namespace -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>$null
        if (![string]::IsNullOrEmpty($externalIP) -and $externalIP -ne "<pending>") {
            return $externalIP
        }
        Start-Sleep -Seconds 10
        $waited += 10
        Write-Host "  Waiting for $ServiceName IP... ($waited/$MaxWaitSeconds seconds)" -ForegroundColor Gray
    }
    return $null
}

# Get public IPs for MCP services
Write-Host "`nRetrieving MCP service public IPs..." -ForegroundColor Yellow
$mcpContractsIP = Get-ServiceExternalIP -ServiceName "mcp-contracts"
$mcpRiskIP = Get-ServiceExternalIP -ServiceName "mcp-risk"
$mcpMarketIP = Get-ServiceExternalIP -ServiceName "mcp-market"

if ([string]::IsNullOrEmpty($mcpContractsIP) -or [string]::IsNullOrEmpty($mcpRiskIP) -or [string]::IsNullOrEmpty($mcpMarketIP)) {
    Write-Host "`n[WARNING] Could not retrieve all MCP service public IPs." -ForegroundColor Yellow
    Write-Host "Check LoadBalancer status with: kubectl get svc -n tools" -ForegroundColor Gray
    Write-Host "`nSkipping Foundry agent deployment." -ForegroundColor Yellow
    $skipAgentDeployment = $true
} else {
    Write-Host "`nMCP Service Public IPs:" -ForegroundColor Green
    Write-Host "  mcp-contracts: $mcpContractsIP" -ForegroundColor White
    Write-Host "  mcp-risk: $mcpRiskIP" -ForegroundColor White
    Write-Host "  mcp-market: $mcpMarketIP" -ForegroundColor White
    $skipAgentDeployment = $false
}

Write-Host "`n=== Deploying Foundry Agents ===" -ForegroundColor Cyan

# Check if Python is available
$pythonAvailable = $true
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Python not found. Skipping Foundry agent deployment." -ForegroundColor Yellow
    Write-Host "To deploy agents later, run:" -ForegroundColor Gray
    Write-Host "  python scripts/deploy_foundry_agents.py --project-endpoint <ENDPOINT> --model-deployment <MODEL>" -ForegroundColor Gray
    $pythonAvailable = $false
}

if ($pythonAvailable -and -not $skipAgentDeployment) {
    # Install Python dependencies for agent deployment
    Write-Host "Installing Python dependencies for agent deployment..." -ForegroundColor Yellow
    pip install -r scripts/requirements-agents.txt --quiet

    # MCP URLs using public IPs (now that services are deployed with LoadBalancer)
    # URLs must end with /mcp for http-streamable protocol
    $mcpContractsUrl = "http://${mcpContractsIP}:8000/mcp"
    $mcpRiskUrl = "http://${mcpRiskIP}:8000/mcp"
    $mcpMarketUrl = "http://${mcpMarketIP}:8000/mcp"
    
    # Default model deployment name - update this based on your Foundry project
    $modelDeployment = "gpt-4o"
    
    Write-Host "`nAgent Configuration:" -ForegroundColor Cyan
    Write-Host "  Project Endpoint: $aiAccountEndpoint" -ForegroundColor White
    Write-Host "  Model Deployment: $modelDeployment" -ForegroundColor White
    Write-Host "  MCP Contracts URL: $mcpContractsUrl" -ForegroundColor White
    Write-Host "  MCP Risk URL: $mcpRiskUrl" -ForegroundColor White
    Write-Host "  MCP Market URL: $mcpMarketUrl" -ForegroundColor White
    Write-Host ""
    
    # Verify MCP services are running before deploying agents
    Write-Host "Verifying MCP services are running..." -ForegroundColor Yellow
    $mcpServicesReady = $true
    $mcpServices = @("mcp-contracts", "mcp-risk", "mcp-market")
    
    foreach ($svc in $mcpServices) {
        $podStatus = kubectl get pods -n tools -l app=$svc -o jsonpath='{.items[0].status.phase}' 2>$null
        if ($podStatus -eq "Running") {
            Write-Host " $svc is running" -ForegroundColor Green
        } else {
            Write-Host "$svc is not ready (status: $podStatus)" -ForegroundColor Yellow
            $mcpServicesReady = $false
        }
    }
    
    if ($mcpServicesReady) {
        # Deploy Foundry agents now that MCP services are available
        Write-Host "`nDeploying autonomous agents to Microsoft Foundry..." -ForegroundColor Yellow
        
        python scripts/deploy_foundry_agents.py `
            --project-endpoint $aiAccountEndpoint `
            --model-deployment $modelDeployment `
            --mcp-contracts-url $mcpContractsUrl `
            --mcp-risk-url $mcpRiskUrl `
            --mcp-market-url $mcpMarketUrl

        if ($LASTEXITCODE -eq 0) {
            Write-Host "`n[OK] Foundry agents deployed successfully" -ForegroundColor Green
        } else {
            Write-Host "`n[WARNING] Foundry agent deployment encountered issues" -ForegroundColor Yellow
            Write-Host "You can deploy agents manually later using:" -ForegroundColor Gray
            Write-Host "  python scripts/deploy_foundry_agents.py --project-endpoint $aiAccountEndpoint --model-deployment $modelDeployment" -ForegroundColor Gray
        }
    } else {
        Write-Host "`n[WARNING] MCP services not fully ready. Skipping agent deployment." -ForegroundColor Yellow
        Write-Host "Deploy agents manually after services are ready:" -ForegroundColor Gray
        Write-Host "  python scripts/deploy_foundry_agents.py --project-endpoint $aiAccountEndpoint --model-deployment $modelDeployment" -ForegroundColor Gray
    }
}

Write-Host "`n4. Deploying Risk Workers..." -ForegroundColor Magenta
helm upgrade --install risk-workers .\k8s\helm\risk-workers `
    --namespace workers --create-namespace `
    --set registry=$acrLoginServer `
    --set image.tag=latest `
    --wait --timeout 10m

Write-Host "`n=== Deployment Summary ===" -ForegroundColor Cyan
Write-Host "[OK] Azure Infrastructure deployed" -ForegroundColor Green
Write-Host "[OK] Container images built and pushed to ACR" -ForegroundColor Green
Write-Host "[OK] Platform components deployed to AKS" -ForegroundColor Green
Write-Host "[OK] RabbitMQ deployed" -ForegroundColor Green
Write-Host "[OK] MCP tool servers deployed" -ForegroundColor Green
Write-Host "[OK] Risk workers deployed with KEDA autoscaling" -ForegroundColor Green

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
