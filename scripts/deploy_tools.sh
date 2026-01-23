#!/bin/bash
# Deploy MCP tool servers

set -e

# Check if ACR is set
if [ -z "$ACR_NAME" ]; then
  echo "Error: ACR_NAME environment variable not set"
  echo "Usage: export ACR_NAME=myacr.azurecr.io && ./deploy_tools.sh"
  exit 1
fi

echo "Deploying MCP tools from $ACR_NAME..."
helm upgrade --install mcp-tools k8s/helm/mcp-tools \
  --namespace tools --create-namespace \
  --set registry=$ACR_NAME \
  --wait

echo "MCP tools deployed successfully!"
echo "Services:"
echo "  - mcp-contracts: kubectl port-forward -n tools svc/mcp-contracts 8001:8000"
echo "  - mcp-risk: kubectl port-forward -n tools svc/mcp-risk 8002:8000"
echo "  - mcp-market: kubectl port-forward -n tools svc/mcp-market 8003:8000"
