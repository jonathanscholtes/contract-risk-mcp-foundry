"""
Demo: EURUSD 2.5% Drop - End-to-End Event-Driven Workflow

This script simulates a complete scenario where:
1. EURUSD drops 2.5%
2. Market feed publishes event
3. Orchestrator detects shock and invokes Foundry agent
4. Agent identifies exposed contracts, submits FX VaR jobs
5. Workers process jobs
6. Agent polls results, flags critical contracts
7. Agent writes risk memos and emits alerts
8. Grafana updates automatically

Usage:
    python scripts/demo_eurusd_shock.py
"""

import asyncio
import httpx
import json
import os
from datetime import datetime
from typing import List, Dict

# Configuration - use environment variables or localhost
MCP_CONTRACTS_URL = os.getenv("MCP_CONTRACTS_URL", "http://localhost:8001")
MCP_RISK_URL = os.getenv("MCP_RISK_URL", "http://localhost:8002")
MCP_MARKET_URL = os.getenv("MCP_MARKET_URL", "http://localhost:8003")

# Color codes for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def log_step(step: str, message: str, color: str = BLUE):
    """Log a step in the demo with color."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{color}{BOLD}[{timestamp}] {step}{RESET} {message}")


def log_event(message: str):
    """Log an event."""
    print(f"{CYAN}📢 {message}{RESET}")


def log_success(message: str):
    """Log a success message."""
    print(f"{GREEN}✓ {message}{RESET}")


def log_warning(message: str):
    """Log a warning message."""
    print(f"{YELLOW}⚠ {message}{RESET}")


def log_critical(message: str):
    """Log a critical alert."""
    print(f"{RED}🚨 {message}{RESET}")


async def simulate_market_shock():
    """Step 1: Market feed publishes EURUSD shock event."""
    log_step("STEP 1", "Market Feed Publishes Event", BLUE)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{MCP_MARKET_URL}/simulate_shock", params={
            "currency_pair": "EURUSD",
            "shock_pct": -2.5
        })
        
        if response.status_code == 200:
            shock_data = response.json()
            log_event(f"EURUSD shock detected: {shock_data['original_spot']:.4f} → {shock_data['shocked_spot']:.4f} (-2.5%)")
            log_success("Market event published to orchestrator")
            return shock_data
        else:
            log_warning(f"Failed to simulate shock: {response.text}")
            return None


async def orchestrator_detects_shock(shock_data: Dict):
    """Step 2: Orchestrator detects shock and prepares agent invocation."""
    log_step("STEP 2", "Orchestrator Detects Market Shock", BLUE)
    
    log_event("Threshold check: 2.5% > 2.0% threshold")
    log_warning("Market shock threshold exceeded!")
    log_success("Preparing to invoke Foundry agent...")
    
    await asyncio.sleep(1)


async def invoke_foundry_agent_simulation(shock_data: Dict):
    """Step 3: Orchestrator invokes Foundry agent (simulated)."""
    log_step("STEP 3", "Orchestrator Invokes Foundry Agent", BLUE)
    
    invocation_payload = {
        "task": "market_shock_assessment",
        "context": {
            "shock_event": shock_data,
            "currency_pair": "EURUSD",
            "shock_pct": -2.5,
            "timestamp": datetime.utcnow().isoformat(),
        },
        "mcp_endpoints": {
            "contracts": MCP_CONTRACTS_URL,
            "risk": MCP_RISK_URL,
            "market": MCP_MARKET_URL,
        }
    }
    
    log_event(f"Invoking agent: market_shock_assessment")
    print(f"   Context: EURUSD -2.5% shock at {datetime.now().strftime('%H:%M:%S')}")
    log_success("Agent invocation successful")
    
    return invocation_payload


async def agent_identifies_contracts():
    """Step 4: Agent identifies exposed contracts."""
    log_step("STEP 4", "Agent: Identify Exposed Contracts", GREEN)
    
    log_event("Agent calling: contracts.search_contracts(currency_pair='EURUSD')")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{MCP_CONTRACTS_URL}/search_contracts", params={
            "currency_pair": "EURUSD"
        })
        
        if response.status_code == 200:
            contracts_data = response.json()
            contracts = contracts_data.get("contracts", [])
            
            log_success(f"Found {len(contracts)} EURUSD contracts")
            for contract in contracts:
                print(f"   • {contract['contract_id']}: {contract['counterparty']}, Notional: ${contract.get('notional_base', 0):,.0f}")
            
            return contracts
        else:
            log_warning("Failed to retrieve contracts")
            return []


async def agent_submits_var_jobs(contracts: List[Dict]):
    """Step 5: Agent submits FX VaR jobs for each contract."""
    log_step("STEP 5", "Agent: Submit FX VaR Jobs", GREEN)
    
    job_ids = []
    
    async with httpx.AsyncClient() as client:
        for contract in contracts:
            contract_id = contract["contract_id"]
            log_event(f"Agent calling: risk.run_fx_var(contract_id='{contract_id}', confidence=0.99)")
            
            response = await client.post(f"{MCP_RISK_URL}/run_fx_var", json={
                "contract_id": contract_id,
                "horizon_days": 1,
                "confidence": 0.99,
                "simulations": 20000
            })
            
            if response.status_code == 200:
                result = response.json()
                job_id = result["job_id"]
                job_ids.append((contract_id, job_id))
                log_success(f"Job submitted: {job_id} for {contract_id}")
            
            await asyncio.sleep(0.5)
    
    return job_ids


async def workers_process_jobs(job_ids: List[tuple]):
    """Step 6: Risk workers process jobs (simulated wait)."""
    log_step("STEP 6", "Risk Workers: Processing Jobs", YELLOW)
    
    log_event(f"Workers consuming {len(job_ids)} jobs from RabbitMQ queue")
    print("   Computing FX VaR with shocked market conditions...")
    
    # Simulate processing time
    for i in range(3):
        await asyncio.sleep(1)
        print(f"   Processing... {(i+1)*33}%")
    
    log_success("All jobs processed, results published to queue")


async def agent_polls_results(job_ids: List[tuple]):
    """Step 7: Agent polls for results."""
    log_step("STEP 7", "Agent: Poll Job Results", GREEN)
    
    results = []
    
    async with httpx.AsyncClient() as client:
        for contract_id, job_id in job_ids:
            log_event(f"Agent calling: risk.get_risk_result(job_id='{job_id}')")
            
            # Simulate polling (in reality, would retry until complete)
            response = await client.get(f"{MCP_RISK_URL}/get_risk_result", params={
                "job_id": job_id
            })
            
            if response.status_code == 200:
                result = response.json()
                # Simulate completed job
                result["status"] = "succeeded"
                result["result"] = {
                    "var": 125000 * (1 + len(results) * 0.3),  # Simulated VaR values
                    "confidence": 0.99,
                    "horizon_days": 1,
                    "as_of": datetime.utcnow().isoformat()
                }
                results.append((contract_id, result))
                var_value = result["result"]["var"]
                log_success(f"Result received: {contract_id} VaR = ${var_value:,.2f}")
            
            await asyncio.sleep(0.5)
    
    return results


async def agent_flags_critical_contracts(results: List[tuple]):
    """Step 8: Agent flags critical contracts exceeding thresholds."""
    log_step("STEP 8", "Agent: Flag Critical Contracts", RED)
    
    FX_VAR_THRESHOLD = 100000
    critical_contracts = []
    
    log_event(f"Checking against threshold: ${FX_VAR_THRESHOLD:,}")
    
    for contract_id, result in results:
        var_value = result["result"]["var"]
        
        if var_value > FX_VAR_THRESHOLD:
            critical_contracts.append((contract_id, var_value))
            log_critical(f"BREACH: {contract_id} VaR ${var_value:,.2f} exceeds ${FX_VAR_THRESHOLD:,}")
        else:
            print(f"   OK: {contract_id} VaR ${var_value:,.2f} within limits")
    
    log_warning(f"Found {len(critical_contracts)} critical contracts requiring attention")
    
    return critical_contracts


async def agent_writes_memos(critical_contracts: List[tuple]):
    """Step 9: Agent writes risk memos for critical contracts."""
    log_step("STEP 9", "Agent: Write Risk Memos", GREEN)
    
    async with httpx.AsyncClient() as client:
        for contract_id, var_value in critical_contracts:
            memo_title = f"URGENT: FX VaR Breach - EURUSD Shock Impact"
            memo_content = f"""
Risk Alert: EURUSD Market Shock Analysis

Contract: {contract_id}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

MARKET EVENT:
- EURUSD dropped 2.5% in current session
- Current volatility elevated to shock levels

RISK METRICS:
- 1-Day 99% FX VaR: ${var_value:,.2f}
- Threshold: $100,000.00
- Breach Amount: ${var_value - 100000:,.2f} ({((var_value / 100000 - 1) * 100):.1f}% over)

RECOMMENDATION:
- Immediate review required
- Consider hedging options (FX forward, options)
- Monitor EURUSD volatility for continued stress
- Escalate to risk committee if shock persists

Generated by AI Risk Agent | Powered by Microsoft Foundry
"""
            
            log_event(f"Agent calling: contracts.write_risk_memo(contract_id='{contract_id}')")
            
            response = await client.post(f"{MCP_CONTRACTS_URL}/write_risk_memo", json={
                "contract_id": contract_id,
                "memo_title": memo_title,
                "memo_content": memo_content,
                "risk_metrics": {
                    "fx_var": var_value,
                    "threshold": 100000,
                    "breach_amount": var_value - 100000
                },
                "breach_alert": True
            })
            
            if response.status_code == 200:
                log_success(f"Risk memo written for {contract_id}")
            
            await asyncio.sleep(0.5)


async def agent_emits_alerts(critical_contracts: List[tuple]):
    """Step 10: Agent emits alerts."""
    log_step("STEP 10", "Agent: Emit Alerts", RED)
    
    log_event(f"Emitting {len(critical_contracts)} high-priority alerts")
    
    for contract_id, var_value in critical_contracts:
        print(f"""
{RED}{'='*60}
🚨 CRITICAL RISK ALERT 🚨
{'='*60}{RESET}
Contract: {contract_id}
FX VaR:   ${var_value:,.2f}
Status:   THRESHOLD BREACH
Action:   IMMEDIATE REVIEW REQUIRED

Alert sent to:
  • Risk Management Team
  • Treasury Desk
  • Compliance Officers
{RED}{'='*60}{RESET}
""")
    
    log_success("All alerts emitted successfully")


async def grafana_updates():
    """Step 11: Grafana dashboards update automatically."""
    log_step("STEP 11", "Grafana: Dashboards Update", CYAN)
    
    log_event("Prometheus scraping metrics from services...")
    await asyncio.sleep(1)
    
    print(f"""
{CYAN}📊 Risk Operations Center - Live Updates:{RESET}

Dashboard: Contract Risk Operations
URL: http://localhost:3000

Panels Updated:
  ✓ Risk Jobs Queue Depth: {len(critical_contracts)} jobs processed
  ✓ Job Throughput: 3 jobs/min
  ✓ Active Risk Workers: 2 → 5 (KEDA autoscaled)
  ✓ Job Processing Duration: p95 = 2.8s
  
Alerts Triggered:
  🚨 3 contracts exceeding FX VaR threshold
  ⚠ EURUSD volatility spike detected
  
Recent Activity:
  • market_shock_assessment completed
  • 3 risk memos generated
  • 3 breach alerts emitted
""")
    
    log_success("Grafana dashboards live and updated")


async def main():
    """Run the complete demo scenario."""
    print(f"""
{BOLD}{BLUE}{'='*70}
Contract Risk Sentinel - Live Demo
EURUSD 2.5% Drop - Event-Driven Workflow
{'='*70}{RESET}

This demo shows the end-to-end event-driven workflow where AKS
orchestrates Foundry agent invocation based on market events.

{YELLOW}Note: This is a simulation. In production:
  - Orchestrator runs continuously in AKS
  - Foundry agents are invoked via real API
  - RabbitMQ handles async job processing
  - KEDA autoscales workers based on queue depth{RESET}

{BOLD}Starting demo...{RESET}
""")
    
    await asyncio.sleep(2)
    
    try:
        # Execute the workflow
        shock_data = await simulate_market_shock()
        if not shock_data:
            return
        
        await asyncio.sleep(1)
        await orchestrator_detects_shock(shock_data)
        
        await asyncio.sleep(1)
        invocation = await invoke_foundry_agent_simulation(shock_data)
        
        await asyncio.sleep(1)
        contracts = await agent_identifies_contracts()
        
        if not contracts:
            log_warning("No contracts found, seeding sample data...")
            return
        
        await asyncio.sleep(1)
        job_ids = await agent_submits_var_jobs(contracts)
        
        await asyncio.sleep(1)
        await workers_process_jobs(job_ids)
        
        await asyncio.sleep(1)
        results = await agent_polls_results(job_ids)
        
        await asyncio.sleep(1)
        critical_contracts = await agent_flags_critical_contracts(results)
        
        if critical_contracts:
            await asyncio.sleep(1)
            await agent_writes_memos(critical_contracts)
            
            await asyncio.sleep(1)
            await agent_emits_alerts(critical_contracts)
        
        await asyncio.sleep(1)
        await grafana_updates()
        
        # Summary
        print(f"""
{BOLD}{GREEN}{'='*70}
Demo Complete! ✓
{'='*70}{RESET}

Summary:
  • Market shock detected: EURUSD -2.5%
  • Contracts analyzed: {len(contracts)}
  • Critical breaches: {len(critical_contracts)}
  • Risk memos generated: {len(critical_contracts)}
  • Alerts emitted: {len(critical_contracts)}
  
The platform demonstrated:
  ✓ Event-driven agent orchestration
  ✓ Controlled autonomy with governance
  ✓ End-to-end observability
  ✓ Automated risk assessment and alerting

{CYAN}Next Steps:
  1. View Grafana dashboards: http://localhost:3000
  2. Check RabbitMQ queues: http://localhost:15672
  3. Review risk memos in contract service
  4. Monitor worker autoscaling: kubectl get pods -n workers{RESET}
""")
        
    except Exception as e:
        log_critical(f"Demo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
