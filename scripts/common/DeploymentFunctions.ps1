# Common deployment functions for Contract Risk MCP Platform
# This module contains shared utilities used across deployment scripts

function Initialize-AzureContext {
    param (
        [Parameter(Mandatory=$true)]
        [string]$Subscription
    )
    
    Write-Host "`n=== Initializing Azure Context ===" -ForegroundColor Cyan
    
    # Clear account context and configure Azure CLI settings
    az account clear
    az config set core.enable_broker_on_windows=false
    az config set core.login_experience_v2=off
    
    # Login to Azure
    az login 
    az account set --subscription $Subscription
    
    Write-Host "Logged into subscription: $Subscription" -ForegroundColor Green
}

function Test-RequiredTools {
    param (
        [string[]]$Tools = @("kubectl", "helm", "kubelogin")
    )
    
    Write-Host "`n=== Checking Required Tools ===" -ForegroundColor Cyan
    
    $missingTools = @()
    
    foreach ($tool in $Tools) {
        try {
            switch ($tool) {
                "kubectl" {
                    $null = kubectl version --client --short 2>$null
                    Write-Host "kubectl found" -ForegroundColor Green
                }
                "helm" {
                    $null = helm version --short 2>$null
                    Write-Host "helm found" -ForegroundColor Green
                }
                "kubelogin" {
                    $null = kubelogin --version 2>$null
                    Write-Host "kubelogin found" -ForegroundColor Green
                }
                "python" {
                    $null = python --version 2>$null
                    Write-Host "python found" -ForegroundColor Green
                }
            }
        } catch {
            Write-Host "$tool not found" -ForegroundColor Red
            $missingTools += $tool
        }
    }
    
    if ($missingTools.Count -gt 0) {
        Write-Host "`n[X] Missing required tools: $($missingTools -join ', ')" -ForegroundColor Red
        Write-Host "`nInstallation instructions:" -ForegroundColor Yellow
        
        if ($missingTools -contains "kubectl") {
            Write-Host "`nkubectl:" -ForegroundColor White
            Write-Host "  az aks install-cli" -ForegroundColor Gray
        }
        
        if ($missingTools -contains "helm") {
            Write-Host "`nhelm:" -ForegroundColor White
            Write-Host "  winget install Helm.Helm" -ForegroundColor Gray
        }
        
        if ($missingTools -contains "kubelogin") {
            Write-Host "`nkubelogin:" -ForegroundColor White
            Write-Host "  az aks install-cli" -ForegroundColor Gray
        }
        
        if ($missingTools -contains "python") {
            Write-Host "`npython:" -ForegroundColor White
            Write-Host "  winget install Python.Python.3.11" -ForegroundColor Gray
        }
        
        throw "Missing required tools. Please install and retry."
    }
    
    Write-Host "All required tools found`n" -ForegroundColor Green
}

function Get-RandomAlphaNumeric {
    param (
        [int]$Length = 12,
        [string]$Seed
    )
    
    $base62Chars = "abcdefghijklmnopqrstuvwxyz123456789"
    
    $md5 = [System.Security.Cryptography.MD5]::Create()
    $seedBytes = [System.Text.Encoding]::UTF8.GetBytes($Seed)
    $hashBytes = $md5.ComputeHash($seedBytes)
    
    $randomString = ""
    for ($i = 0; $i -lt $Length; $i++) {
        $index = $hashBytes[$i % $hashBytes.Length] % $base62Chars.Length
        $randomString += $base62Chars[$index]
    }
    
    return $randomString
}

function New-SecurePassword {
    param (
        [int]$Length = 16
    )
    
    $chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*'
    return -join ((1..$Length) | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
}

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

function Get-ServiceExternalIP {
    param (
        [string]$ServiceName,
        [string]$Namespace = "tools",
        [int]$MaxWaitSeconds = 180
    )
    
    $waited = 0
    while ($waited -lt $MaxWaitSeconds) {
        $externalIP = (kubectl get svc $ServiceName -n $Namespace -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>$null)
        if (![string]::IsNullOrWhiteSpace($externalIP) -and $externalIP -ne "<pending>") {
            return $externalIP.Trim()
        }
        Start-Sleep -Seconds 10
        $waited += 10
        Write-Host "  Waiting for $ServiceName IP... ($waited/$MaxWaitSeconds seconds)" -ForegroundColor Gray
    }
    return $null
}

function New-FederatedIdentityCredential {
    param (
        [string]$ServiceAccountName,
        [string]$Namespace = "tools",
        [string]$ManagedIdentityName,
        [string]$ResourceGroupName,
        [string]$OidcIssuer
    )
    
    $credentialName = "$ServiceAccountName-federated-id"
    $subject = "system:serviceaccount:${Namespace}:${ServiceAccountName}"
    
    $existingCred = az identity federated-credential show `
        --name $credentialName `
        --identity-name $ManagedIdentityName `
        --resource-group $ResourceGroupName `
        2>$null
    
    if ($null -eq $existingCred) {
        Write-Host "Creating federated identity credential for $ServiceAccountName..." -ForegroundColor Yellow
        az identity federated-credential create `
            --name $credentialName `
            --identity-name $ManagedIdentityName `
            --resource-group $ResourceGroupName `
            --issuer $OidcIssuer `
            --subject $subject `
            --audience "api://AzureADTokenExchange" `
            --output none
        Write-Host "Federated identity credential created for $ServiceAccountName" -ForegroundColor Green
    } else {
        Write-Host "Federated identity credential already exists for $ServiceAccountName" -ForegroundColor Green
    }
}

Export-ModuleMember -Function @(
    'Initialize-AzureContext',
    'Test-RequiredTools',
    'Get-RandomAlphaNumeric',
    'New-SecurePassword',
    'Invoke-HelmWithRetry',
    'Get-ServiceExternalIP',
    'New-FederatedIdentityCredential'
)
