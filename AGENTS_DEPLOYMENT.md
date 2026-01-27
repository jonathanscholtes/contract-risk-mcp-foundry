# Agent Architecture Reference

This document describes the autonomous agents that power the Contract Risk Sentinel platform.

## Overview

The platform uses **three autonomous agents** hosted in Microsoft Azure AI Foundry:

1. **ThresholdBreachAnalyst** - Responds to risk metric violations
2. **MarketShockAnalyst** - Analyzes portfolio impact after market movements
3. **PortfolioScanAnalyst** - Runs scheduled comprehensive risk scans

These agents are invoked on-demand by the AKS orchestrator and coordinate workflows using MCP tools.

## Deployment

Agents are automatically deployed via the main deployment script:

```powershell
.\deploy.ps1 `
    -Subscription 'YOUR_SUBSCRIPTION_NAME' `
    -Location 'eastus2' `
    -UserObjectId 'YOUR_USER_OBJECT_ID'
```

This deploys Azure infrastructure, builds containers, deploys MCP services, and creates all three Foundry agents with proper MCP tool configurations.

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

## Configuration

### Adjusting Thresholds

Update risk thresholds in the orchestrator:

```bash
kubectl set env deployment/agent-orchestrator -n tools \
    FX_VAR_THRESHOLD=150000 \
    IR_DV01_THRESHOLD=60000 \
    MARKET_SHOCK_THRESHOLD=2.5
```

### Modifying Agent Behavior

Agent instructions are defined in `scripts/deploy_foundry_agents.py`. After editing, redeploy agents using deploy.ps1 or the deployment script directly.

## Monitoring

**View agent execution logs:**
- Azure AI Foundry Portal → Agents section → Select agent → Execution history

**View orchestrator logs:**
```bash
kubectl logs -n tools deployment/agent-orchestrator --follow
```

**Check MCP service health:**
```bash
kubectl get pods -n tools
kubectl get svc -n tools
```

**Grafana dashboards:**
Access at `http://<grafana-ip>:3000` to view real-time metrics for agent invocations, queue depth, and worker scaling.

## Resources

- [Azure AI Foundry Documentation](https://learn.microsoft.com/en-us/azure/ai-foundry/)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- Main README: [README.md](README.md)
