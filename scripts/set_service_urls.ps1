# Get current MCP service external IPs and set environment variables
Write-Host "Retrieving MCP service URLs..." -ForegroundColor Cyan

$mcpContractsIP = (kubectl get svc mcp-contracts -n tools -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>$null).Trim()
$mcpRiskIP = (kubectl get svc mcp-risk -n tools -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>$null).Trim()
$mcpMarketIP = (kubectl get svc mcp-market -n tools -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>$null).Trim()

if (![string]::IsNullOrWhiteSpace($mcpContractsIP)) {
    $env:MCP_CONTRACTS_URL = "http://${mcpContractsIP}:8000"
    Write-Host "MCP_CONTRACTS_URL = $env:MCP_CONTRACTS_URL" -ForegroundColor Green
} else {
    Write-Host "MCP Contracts IP not available - using localhost:8001" -ForegroundColor Yellow
    $env:MCP_CONTRACTS_URL = "http://localhost:8001"
}

if (![string]::IsNullOrWhiteSpace($mcpRiskIP)) {
    $env:MCP_RISK_URL = "http://${mcpRiskIP}:8000"
    Write-Host "MCP_RISK_URL = $env:MCP_RISK_URL" -ForegroundColor Green
} else {
    Write-Host "MCP Risk IP not available - using localhost:8002" -ForegroundColor Yellow
    $env:MCP_RISK_URL = "http://localhost:8002"
}

if (![string]::IsNullOrWhiteSpace($mcpMarketIP)) {
    $env:MCP_MARKET_URL = "http://${mcpMarketIP}:8000"
    Write-Host "MCP_MARKET_URL = $env:MCP_MARKET_URL" -ForegroundColor Green
} else {
    Write-Host "MCP Market IP not available - using localhost:8003" -ForegroundColor Yellow
    $env:MCP_MARKET_URL = "http://localhost:8003"
}

Write-Host "`nEnvironment variables set. Run your Python scripts now.`n" -ForegroundColor Cyan
