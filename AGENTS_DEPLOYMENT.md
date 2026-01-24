# Deploying Autonomous Agents to Microsoft Foundry

This guide explains how to deploy and manage autonomous agents for the Contract Risk Sentinel platform in Microsoft Foundry.

## Overview

The platform uses **three autonomous agents** hosted in Microsoft Foundry:

1. **ThresholdBreachAnalyst** - Analyzes contracts exceeding risk thresholds
2. **MarketShockAnalyst** - Performs portfolio-wide reassessment after market shocks
3. **PortfolioScanAnalyst** - Runs scheduled comprehensive risk scans

These agents are invoked on-demand by the AKS orchestrator and use MCP tools to access contract data, submit risk calculations, and retrieve market information.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AKS Orchestrator                         │
│  - Detects events (thresholds, shocks, schedules)          │
│  - Invokes Foundry agents via API                          │
│  - Monitors results and triggers follow-ups                │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ HTTPS API Call
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Microsoft Foundry Agents                       │
│  ┌─────────────────┬──────────────────┬──────────────────┐ │
│  │  Threshold      │  Market Shock    │  Portfolio Scan  │ │
│  │  Breach         │  Analyst         │  Analyst         │ │
│  │  Analyst        │                  │                  │ │
│  └─────────────────┴──────────────────┴──────────────────┘ │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ MCP Protocol
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  MCP Tool Servers (AKS)                     │
│  ┌─────────────────┬──────────────────┬──────────────────┐ │
│  │  mcp-contracts  │  mcp-risk        │  mcp-market      │ │
│  │  - Contracts    │  - Submit jobs   │  - FX rates      │ │
│  │  - Memos        │  - Get results   │  - Volatility    │ │
│  └─────────────────┴──────────────────┴──────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Azure AI Foundry Project** - Create a project in Azure AI Foundry
2. **Model Deployment** - Deploy a model (e.g., GPT-4o) in your Foundry project
3. **Python 3.10+** with required packages
4. **Azure CLI** authenticated to your subscription
5. **Deployed MCP Services** - MCP tool servers running in AKS

## Quick Start - Integrated Deployment

The easiest way to deploy agents is as part of the main deployment process:

```powershell
.\deploy.ps1 `
    -Subscription 'YOUR_SUBSCRIPTION_NAME' `
    -Location 'eastus2' `
    -UserObjectId 'YOUR_USER_OBJECT_ID'
```

This will:
1. Deploy Azure infrastructure (AKS, Cosmos DB, AI Foundry, etc.)
2. Build and push container images to ACR
3. Deploy MCP services to AKS
4. **Automatically deploy Foundry agents** (new step!)
5. Configure Helm charts with agent endpoints

## Manual Agent Deployment

To deploy agents separately or update existing agents:

### 1. Install Dependencies

```bash
pip install -r scripts/requirements-agents.txt
```

### 2. Set Environment Variables

Create a `.env` file based on `.env.example.agents`:

```bash
PROJECT_ENDPOINT=https://your-project.api.azureml.ms
MODEL_DEPLOYMENT_NAME=gpt-4o
MCP_CONTRACTS_URL=http://mcp-contracts.tools.svc.cluster.local:8000/mcp
MCP_RISK_URL=http://mcp-risk.tools.svc.cluster.local:8000/mcp
MCP_MARKET_URL=http://mcp-market.tools.svc.cluster.local:8000/mcp
```

**Note**: MCP URLs must end with `/mcp` for http-streamable protocol support.

### 3. Deploy Agents

```bash
python scripts/deploy_foundry_agents.py \
    --project-endpoint "https://your-project.api.azureml.ms" \
    --model-deployment "gpt-4o" \
    --mcp-contracts-url "http://mcp-contracts.tools.svc.cluster.local:8000/mcp" \
    --mcp-risk-url "http://mcp-risk.tools.svc.cluster.local:8000/mcp" \
    --mcp-market-url "http://mcp-market.tools.svc.cluster.local:8000/mcp"
```

### 4. Update AKS Configuration

After agent deployment, update the Kubernetes secret with agent details:

```bash
# Get your Foundry API key from Azure Portal
FOUNDRY_API_KEY="your-api-key-here"

# Create or update the secret
kubectl create secret generic foundry-agent-secret -n tools \
    --from-literal=endpoint="https://your-project.api.azureml.ms" \
    --from-literal=api-key="$FOUNDRY_API_KEY" \
    --dry-run=client -o yaml | kubectl apply -f -
```

### 5. Test Agent Invocation

```bash
python scripts/test_agent_invocation.py \
    --project-endpoint "https://your-project.api.azureml.ms" \
    --agent-name "ThresholdBreachAnalyst"
```

## Agent Details

### ThresholdBreachAnalyst

**Trigger**: Risk calculation exceeds configured thresholds (FX VaR > $100k or IR DV01 > $50k)

**Workflow**:
1. Receives breach context (contract_id, risk_result, breach_details)
2. Retrieves full contract details via `get_contract()`
3. Analyzes breach severity using market data
4. Generates hedge recommendations
5. Persists risk memo via `write_risk_memo()`

**MCP Tools Used**:
- `contracts.get_contract`
- `contracts.write_risk_memo`
- `market.get_fx_spot`
- `market.get_market_snapshot`

### MarketShockAnalyst

**Trigger**: Significant market movement detected (e.g., EURUSD drops 2.5%)

**Workflow**:
1. Receives shock event (currency_pair, shock_pct, timestamp)
2. Identifies exposed contracts via `search_contracts()`
3. Submits risk recalculations using `run_fx_var()` for each contract
4. Polls for results using `get_risk_result()`
5. Aggregates portfolio-wide impact
6. Writes risk memos for critical contracts
7. Prioritizes action items

**MCP Tools Used**:
- `contracts.search_contracts`
- `risk.run_fx_var`
- `risk.get_risk_result`
- `contracts.write_risk_memo`
- `market.get_market_snapshot`

### PortfolioScanAnalyst

**Trigger**: Scheduled (daily at 8 AM UTC, intraday every 4 hours)

**Workflow**:
1. Retrieves all active contracts
2. Gets current market snapshot
3. Submits risk calculations for entire portfolio
4. Polls for all results
5. Generates executive summary with:
   - Total portfolio VaR and DV01
   - Top 10 riskiest contracts
   - Threshold breach summary
   - Trend analysis
6. Writes portfolio-level risk memo

**MCP Tools Used**:
- `contracts.search_contracts`
- `risk.run_fx_var`
- `risk.run_ir_dv01`
- `risk.get_risk_result`
- `contracts.write_risk_memo`
- `market.get_market_snapshot`

## Configuring Agent Behavior

### Thresholds

Update thresholds in the AKS orchestrator environment:

```bash
kubectl set env deployment/agent-orchestrator -n tools \
    FX_VAR_THRESHOLD=150000 \
    IR_DV01_THRESHOLD=60000 \
    MARKET_SHOCK_THRESHOLD=2.5
```

### Agent Instructions

To modify agent behavior, edit the instructions in `scripts/deploy_foundry_agents.py`:
- Line ~100: ThresholdBreachAnalyst instructions
- Line ~185: MarketShockAnalyst instructions  
- Line ~285: PortfolioScanAnalyst instructions

Then redeploy the agents.

### Model Selection

Change the model used by agents:

```bash
python scripts/deploy_foundry_agents.py \
    --model-deployment "gpt-4o-mini"  # Use a different model
```

## Monitoring & Troubleshooting

### View Agent Logs (in Foundry Portal)

1. Navigate to Azure AI Foundry Portal
2. Select your project
3. Go to "Agents" section
4. Click on an agent to view execution history

### View Orchestrator Logs (in AKS)

```bash
kubectl logs -n tools deployment/agent-orchestrator --follow
```

### Test MCP Connectivity

From within the cluster:

```bash
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
    curl http://mcp-contracts.tools.svc.cluster.local:8000/health
```

### Common Issues

**Issue**: Agent deployment fails with authentication error
**Solution**: Ensure you're logged in with `az login` and have appropriate permissions

**Issue**: Agents can't reach MCP services
**Solution**: Verify MCP services are running:
```bash
kubectl get pods -n tools
kubectl get svc -n tools
```

**Issue**: Agent invocation times out
**Solution**: Increase timeout in orchestrator (default 300s):
```python
async with httpx.AsyncClient(timeout=600.0) as client:
```

## Agent Lifecycle Management

### Updating Agents

1. Modify agent instructions in `deploy_foundry_agents.py`
2. Redeploy:
```bash
python scripts/deploy_foundry_agents.py \
    --project-endpoint "https://your-project.api.azureml.ms" \
    --model-deployment "gpt-4o"
```

This creates a new version of each agent. The orchestrator will automatically use the latest version.

### Deleting Agents

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

client = AIProjectClient(
    endpoint="https://your-project.api.azureml.ms",
    credential=DefaultAzureCredential(),
)

client.agents.delete_version(
    agent_name="ThresholdBreachAnalyst",
    agent_version="1"
)
```

### Agent Versioning

Agents support versioning. When you redeploy, a new version is created. To use a specific version:

```python
# In orchestrator.py
response = openai_client.responses.create(
    conversation=conversation.id,
    input=prompt,
    extra_body={
        "agent": {
            "name": "ThresholdBreachAnalyst",
            "version": "2",  # Specify version
            "type": "agent_reference"
        }
    },
)
```

## Security Considerations

1. **API Keys**: Store Foundry API keys in Kubernetes secrets, not in code
2. **RBAC**: Use Azure RBAC to control who can deploy/modify agents
3. **MCP Tool Approval**: Set to `"never"` for production (already configured)
4. **Network Policies**: Restrict agent-to-MCP communication to specific namespaces
5. **Audit Logs**: Enable diagnostic logging in Foundry for compliance

## Cost Optimization

1. **Right-size Model**: Consider using GPT-4o-mini for less complex tasks
2. **Batching**: Portfolio scan agent processes contracts in batches
3. **Caching**: MCP services cache market data to reduce redundant calls
4. **Timeouts**: Agents have 5-minute timeout to prevent runaway costs

## Next Steps

1. ✅ Deploy agents using the integrated deployment script
2. ✅ Test agent invocation with sample data
3. ✅ Configure AKS orchestrator with agent endpoints
4. ⬜ Seed test contracts: `python scripts/seed_contracts.py`
5. ⬜ Run market shock demo: `python scripts/demo_eurusd_shock.py`
6. ⬜ Monitor agents in Grafana dashboards

## Resources

- [Azure AI Foundry Documentation](https://learn.microsoft.com/en-us/azure/ai-foundry/)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [Agent Orchestration Best Practices](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/)
- Project README: [README.md](../README.md)

## Support

For issues or questions:
1. Check orchestrator logs: `kubectl logs -n tools deployment/agent-orchestrator`
2. Review agent execution history in Foundry Portal
3. Test MCP service health endpoints
4. Verify Kubernetes secret configuration
