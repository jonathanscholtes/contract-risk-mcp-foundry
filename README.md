> ⚠️  
> **This project is currently in active development and may contain breaking changes.**  
> Updates and modifications are being made frequently, which may impact stability or functionality. This notice will be removed once development is complete and the project reaches a stable release.  

# From Chatbots to Autonomous Agents: Building an Always-On Risk Platform

📝 **Read the full walkthrough**: [Blog Article](https://your-blog-url.com)

An **autonomous agentic system** demonstrating production-ready AI agent orchestration for continuous financial contract risk monitoring.

**Built with:**
- **Microsoft Azure AI Foundry** - Autonomous agent hosting and orchestration
- **MCP (Model Context Protocol)** - Standardized tool-calling interface
- **Azure Kubernetes Service (AKS)** - Scalable compute and event orchestration
- **Azure DocumentDB (MongoDB)** - Flexible contract and risk memo storage
- **RabbitMQ** - Asynchronous job queue for risk calculations
- **Grafana/Prometheus/OpenTelemetry** - Production-grade observability

## 🎯 Overview

This platform demonstrates an **autonomous agentic system** that continuously monitors financial contracts for **FX and Interest Rate risk**. The system operates without human intervention, automatically:

- **Detecting events**: Market shocks, threshold breaches, scheduled scans
- **Invoking AI agents**: Foundry agents autonomously analyze risk exposure
- **Calculating risk metrics**: FX VaR, IR DV01, stress tests via async workers
- **Generating insights**: AI-written risk memos with hedge recommendations
- **Scaling dynamically**: Workers autoscale based on workload (KEDA)
- **Full observability**: Real-time metrics, distributed tracing, dashboards

**Key Architectural Pattern**: Event-driven orchestration where AKS detects events and invokes Foundry agents, which coordinate workflows using MCP tools. Agents operate with **controlled autonomy** - they make decisions within defined boundaries while maintaining full auditability.

## 📐 Architecture

![design](/media/diagram2.png)
---


### Components

**AKS Orchestration Layer** (Event Detection & Scheduling)
- `agent-orchestrator`: Event-driven agent invocation service
  - Detects events (RabbitMQ messages, market shocks, threshold breaches)
  - Runs cron-based portfolio scans and market data updates
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
- `MongoDB (DocumentDB)`: Flexible storage for contracts and risk memos
- `RabbitMQ`: Job/result queues with DLQ support
- `Prometheus`: Metrics collection
- `Grafana`: Risk operations dashboards
- `OpenTelemetry`: Distributed tracing

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



## 🚀 Deployment

### Prerequisites

- Azure subscription with AI Foundry access
- Azure Container Registry (ACR)
- `kubectl`, `helm`, Azure CLI
- Python 3.10+


```powershell
.\deploy.ps1 `
    -Subscription 'YOUR_SUBSCRIPTION_NAME' `
    -Location 'eastus2' `
    -UserObjectId 'YOUR_USER_OBJECT_ID'
```

**Parameter Details:**
- `Subscription`: Your Azure subscription name (required)
- `Location`: Azure region for resources, default is `eastus2` (optional)
- `UserObjectId`: (Optional) Your Azure AD user object ID for AKS cluster admin access. Get it via:
  ```powershell
  az ad signed-in-user show --query id -o tsv
  ```

This deployment will:
- ✅ Deploy Azure infrastructure (AKS, MongoDB, AI Foundry, ACR)
- ✅ Build and push container images
- ✅ Deploy MCP tool servers to AKS
- ✅ Deploy autonomous agents to Microsoft Foundry
- ✅ Configure RabbitMQ and workers
- ✅ Set up monitoring (Prometheus, Grafana, OpenTelemetry)

**📖 For detailed agent deployment documentation, see [AGENTS_DEPLOYMENT.md](AGENTS_DEPLOYMENT.md)**

## 📊 Next Steps

After deployment completes, explore the system:

### 1. Access Grafana Dashboards

```powershell
# Forward Grafana port
kubectl port-forward -n platform svc/grafana 3000:3000

# Open in browser: http://localhost:3000
# Default credentials: admin / admin
```

Navigate to **"Contract Risk Operations Center - Enhanced"** dashboard to see:
- Real-time risk metrics and contract VaR values
- Job submission and completion rates
- Pending jobs gauge
- Agent invocation logs

### 2. Check Agent Logs

```powershell
# View orchestrator logs (event detection and agent invocation)
kubectl logs -n tools deployment/agent-orchestrator --tail=100 -f

# View specific agent invocation
kubectl logs -n tools deployment/agent-orchestrator | grep "Agent Invocation"

# Check market shock detections
kubectl logs -n tools deployment/agent-orchestrator | grep "Market Shock"
```

### 3. Monitor Job Queue

```powershell
# Access RabbitMQ management console
kubectl port-forward -n rabbitmq svc/rabbitmq 15672:15672

# Open in browser: http://localhost:15672
# Default credentials: guest / guest

# Check queues and messages:
# - risk.jobs (incoming risk calculation requests)
# - risk.results (completed calculations)
```

---
<details>

<summary>Workflow</summary>


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

</details>

---

## ♻️ **Clean-Up**

After completing testing or when no longer needed, ensure you delete any unused Azure resources or remove the entire Resource Group to avoid additional charges.

---

## 📜 License  
This project is licensed under the [MIT License](LICENSE.md), granting permission for commercial and non-commercial use with proper attribution.

---

## ⚠️ Disclaimer  

**THIS CODE IS PROVIDED FOR EDUCATIONAL AND DEMONSTRATION PURPOSES ONLY.**

This sample code is not intended for production use and is provided "AS IS", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with the software or the use or other dealings in the software.

**Key Points:**
- This is a **demonstration project** showcasing autonomous agentic architecture patterns
- **Not intended for production financial risk management** without significant additional development, testing, and compliance review
- Risk calculations are simplified models for demonstration purposes only
- Users are responsible for ensuring compliance with applicable regulations and security requirements
- Microsoft Azure services incur costs - monitor your usage and clean up resources when done
- No warranties or guarantees are provided regarding accuracy, reliability, or suitability for any purpose

By using this code, you acknowledge that you understand these limitations and accept full responsibility for any consequences of its use.
