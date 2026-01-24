# Contract Risk Sentinel

An always-on contract risk monitoring platform built with:
- **Microsoft Foundry Agents** for orchestration and analysis
- **MCP (Model Context Protocol)** for tool-calling
- **AKS (Azure Kubernetes Service)** for scalable compute
- **RabbitMQ** for queue-driven job processing
- **Grafana/Prometheus/OTel** for comprehensive observability

## 🎯 Overview

This platform continuously monitors a portfolio of financial contracts for **FX and Interest Rate risk**, providing:
- Real-time risk metrics (FX VaR, IR DV01, stress tests)
- Automated threshold breach alerts
- AI-generated risk memos and hedge recommendations
- Production-grade observability and autoscaling

## 🏗️ Architecture

### Components

**AKS Orchestration Layer** (Event Detection & Scheduling)
- `agent-orchestrator`: Event-driven agent invocation service
  - Detects events (RabbitMQ messages, market shocks, threshold breaches)
  - Runs cron-based portfolio scans
  - Invokes Foundry agents via API
  - Provides controlled autonomy with full observability

**Foundry Agents** (Hosted in Microsoft Foundry)
- Invoked by AKS on-demand
- Coordinate risk analysis workflows
- Generate narratives and recommendations
- Call MCP tools for data and computation

**MCP Tool Servers** (Data & Job Submission Layer)
- `mcp-contracts`: Contract registry and risk memo storage
- `mcp-market`: Market data snapshots (FX rates, volatility)
- `mcp-risk`: Risk job submission and result retrieval

**AKS Workers** (Compute Layer)
- `risk-worker`: Executes FX VaR, IR DV01, and stress tests
- Consumes jobs from RabbitMQ
- Autoscales based on queue depth (KEDA)

**Infrastructure**
- `RabbitMQ`: Job/result queues with DLQ support
- `Prometheus`: Metrics collection
- `Grafana`: Risk operations dashboards
- `OpenTelemetry`: Distributed tracing

### Workflow

**Event-Driven Agent Invocation:**

1. **AKS orchestrator** detects event:
   - Cron schedule triggers daily portfolio scan
   - Risk result exceeds threshold
   - Market shock detected
   - New contract added

2. **Orchestrator invokes Foundry agent** via API with context:
   - Event details and parameters
   - MCP endpoint URLs for tool access

3. **Foundry agent** executes workflow:
   - Calls `contracts.search_contracts()` to get portfolio
   - Calls `risk.run_fx_var()` for each contract → returns `job_id`
   - Polls `risk.get_risk_result(job_id)` until complete
   - Analyzes results and generates recommendations
   - Calls `contracts.write_risk_memo()` to persist analysis

4. **Risk workers** process async jobs:
   - Consume from RabbitMQ
   - Compute VaR/DV01
   - Publish results back to queue

5. **Orchestrator** monitors results:
   - Detects threshold breaches
   - Triggers follow-up agent invocations if needed

6. **Grafana** shows real-time metrics and alerts

## 🚀 Quick Start

### Prerequisites

- Azure subscription with AI Foundry access
- Azure Container Registry (ACR)
- `kubectl`, `helm`, Azure CLI
- Python 3.10+

### Automated Deployment

```powershell
.\deploy.ps1 `
    -Subscription 'YOUR_SUBSCRIPTION_NAME' `
    -Location 'eastus2' `
    -UserObjectId 'YOUR_USER_OBJECT_ID'
```

This automated deployment will:
- ✅ Deploy Azure infrastructure (AKS, Cosmos DB, AI Foundry, ACR)
- ✅ Build and push container images
- ✅ Deploy MCP tool servers to AKS
- ✅ Deploy autonomous agents to Microsoft Foundry
- ✅ Configure RabbitMQ and workers
- ✅ Set up monitoring (Prometheus, Grafana, OpenTelemetry)

**📖 For detailed agent deployment documentation, see [AGENTS_DEPLOYMENT.md](AGENTS_DEPLOYMENT.md)**

### Manual Step-by-Step Deployment

### 1. Bootstrap Cluster

```bash
cd scripts
./bootstrap_cluster.sh
```

### 2. Deploy Platform Components

```bash
./deploy_platform.sh
./deploy_rabbitmq.sh
```

### 3. Build and Push Images

```bash
export ACR_NAME=myacr.azurecr.io
az acr login --name myacr

# Build all images
docker build -t $ACR_NAME/agent-orchestrator:0.1.0 -f apps/agent-orchestrator/Dockerfile .
docker build -t $ACR_NAME/mcp-contracts:0.1.0 -f apps/mcp-contracts/Dockerfile .
docker build -t $ACR_NAME/mcp-risk:0.1.0 -f apps/mcp-risk/Dockerfile .
docker build -t $ACR_NAME/mcp-market:0.1.0 -f apps/mcp-market/Dockerfile .
docker build -t $ACR_NAME/risk-worker:0.1.0 -f apps/risk-worker/Dockerfile .

# Push all images
docker push $ACR_NAME/agent-orchestrator:0.1.0
docker push $ACR_NAME/mcp-contracts:0.1.0
docker push $ACR_NAME/mcp-risk:0.1.0
docker push $ACR_NAME/mcp-market:0.1.0
docker push $ACR_NAME/risk-worker:0.1.0
```

### 4. Deploy Services

```bash
export ACR_NAME=myacr.azurecr.io
./deploy_tools.sh
./deploy_workers.sh
```

### 5. Access Services

```bash
# Grafana
kubectl port-forward -n platform svc/grafana 3000:3000
# Access at http://localhost:3000 (admin/admin)

# RabbitMQ Management UI
kubectl port-forward -n rabbitmq svc/rabbitmq 15672:15672
# Access at http://localhost:15672 (user/password)

# MCP Tools (for testing)
kubectl port-forward -n tools svc/mcp-contracts 8001:8000
kubectl port-forward -n tools svc/mcp-risk 8002:8000
kubectl port-forward -n tools svc/mcp-market 8003:8000

# Agent Orchestrator logs
kubectl logs -n tools deployment/agent-orchestrator -f
```

### 6. Seed Data and Test

```bash
# Seed sample contracts
python scripts/seed_contracts.py

# Run market simulations
python scripts/simulate_market.py

# Load test the platform
python scripts/load_test_tools.py
```

## 📊 Monitoring

Open Grafana at http://localhost:3000 to view the **Risk Operations Center** dashboard:

- **Queue Depth**: Real-time view of pending risk jobs
- **Job Throughput**: Jobs published vs. consumed
- **Worker Count**: Active risk workers (KEDA autoscaling)
- **Processing Duration**: Job latency (p50, p95)

## 🔧 Local Development

For local development without Kubernetes:

```bash
# Start RabbitMQ
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management

# Run MCP servers
cd apps/mcp-contracts
pip install -e .
python -m src.main

# Run risk worker
cd apps/risk-worker
pip install -e .
export RABBITMQ_HOST=localhost
python -m src.worker
```

## 🛠️ MCP Tool Reference

### contracts.search_contracts
Search for contracts by type, counterparty, or currency pair.

### contracts.get_contract
Retrieve details for a specific contract.

### contracts.create_contract
Create a new contract in the registry.

### contracts.write_risk_memo
Store a risk assessment memo for a contract.

### contracts.get_risk_memos
Retrieve all risk memos for a contract.

### risk.run_fx_var
Submit an FX VaR calculation job (async).

### risk.run_ir_dv01
Submit an IR DV01 calculation job (async).

### risk.get_risk_result
Poll for job result by job_id.

### risk.list_jobs
List all jobs, optionally filtered by status.

### market.get_fx_spot
Get current FX spot rate for a currency pair.

### market.get_fx_volatility
Get annualized volatility for a currency pair.

### market.get_market_snapshot
Get snapshot of all market data.

### market.simulate_shock
Simulate a market shock scenario.

## 📁 Project Structure

```
contract-risk-mcp-foundry/
├── apps/                      # Application services
│   ├── agent-orchestrator/    # Event-driven agent invocation
│   ├── mcp-contracts/         # Contract registry MCP server
│   ├── mcp-risk/              # Risk job submission MCP server
│   ├── mcp-market/            # Market data MCP server
│   └── risk-worker/           # Risk calculation worker
├── shared/                    # Shared Pydantic schemas
│   └── contracts/             # Contract, job, result models
├── k8s/                       # Kubernetes resources
│   └── helm/                  # Helm charts
│       ├── platform/          # Monitoring stack
│       ├── mcp-tools/         # MCP servers
│       └── risk-workers/      # Workers + KEDA
├── observability/             # Observability configs
│   ├── grafana/               # Dashboards and datasources
│   ├── prometheus/            # Prometheus config
│   └── otel/                  # OpenTelemetry config
├── scripts/                   # Deployment and testing scripts
└── infra/                     # Bicep infrastructure (optional)
```

## 🎯 Demo Scenarios

### EURUSD 2.5% Shock - Complete Workflow
```bash
python scripts/demo_eurusd_shock.py
```

This demo shows the complete event-driven workflow:

1. **Market Event**: EURUSD drops 2.5%
2. **Orchestrator Detects**: Shock exceeds 2.0% threshold
3. **Agent Invoked**: Foundry agent receives market_shock_assessment task
4. **Agent Workflow**:
   - Identifies 2+ exposed EURUSD contracts
   - Submits FX VaR jobs to risk service
   - Polls for results (workers process via RabbitMQ)
   - Flags 3 contracts as critical (VaR > $100k)
   - Writes detailed risk memos
   - Emits high-priority alerts
5. **Grafana Updates**: Real-time dashboard shows queue, workers, alerts

Watch for:
- Worker autoscaling (2 → 5 pods)
- Queue depth spike and drain
- Breach alerts in dashboard
- Risk memos generated

### FX Shock Day (Manual)
```bash
python scripts/simulate_market.py
# Simulates EURUSD -3% shock
# Watch Grafana for:
#   - Queue spike
#   - Worker autoscaling
#   - Breach memos
```

### Rate Jump
```bash
# Simulate +75 bps parallel shift
# Compute DV01 across portfolio
# Generate ranked exposure summary
```

## 🔐 Security Considerations

For production deployments:
- Store RabbitMQ credentials in Azure Key Vault
- Use managed identities for ACR access
- Enable APIM in front of MCP endpoints for auth/quotas
- Configure network policies for pod-to-pod communication

## 📈 Scaling

The platform autoscales automatically:
- **KEDA** monitors RabbitMQ queue depth
- Workers scale from 2 to 10 replicas based on load
- MCP servers can be manually scaled via Helm values

## 🛣️ Roadmap

### Phase 1 - MVP ✅
- Simulated contracts and market feed
- Basic FX VaR and IR DV01 calculations
- RabbitMQ job queue
- Grafana dashboards

### Phase 2 - Production-grade
- Persistent database (Cosmos DB / PostgreSQL)
- Idempotency enforcement
- Retry policies and DLQ workflows
- APIM integration

### Phase 3 - Advanced Risk
- Historical stress library
- Correlated simulations
- PFE approximation
- Human-in-the-loop approval workflows

## 📝 License

MIT License - see LICENSE file for details

## 🤝 Contributing

Contributions are welcome! Please see CONTRIBUTING.md for guidelines.

## 📧 Contact

For questions or support, please open an issue on GitHub.
