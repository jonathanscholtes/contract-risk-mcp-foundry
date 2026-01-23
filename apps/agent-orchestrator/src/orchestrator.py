"""Agent Orchestrator - Event-driven agent invocation service.

This service runs in AKS and:
- Detects events (RabbitMQ messages, market shocks, threshold breaches)
- Runs scheduled portfolio scans
- Invokes Foundry agents via API
- Provides controlled autonomy with full observability
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))

import os
import json
import asyncio
import aio_pika
import httpx
from datetime import datetime, time
from typing import Dict, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

FOUNDRY_AGENT_ENDPOINT = os.getenv("FOUNDRY_AGENT_ENDPOINT", "https://foundry-agent-url.com/invoke")
FOUNDRY_API_KEY = os.getenv("FOUNDRY_API_KEY", "")

MCP_CONTRACTS_URL = os.getenv("MCP_CONTRACTS_URL", "http://mcp-contracts.tools.svc.cluster.local:8000")
MCP_RISK_URL = os.getenv("MCP_RISK_URL", "http://mcp-risk.tools.svc.cluster.local:8000")
MCP_MARKET_URL = os.getenv("MCP_MARKET_URL", "http://mcp-market.tools.svc.cluster.local:8000")

# Thresholds
FX_VAR_THRESHOLD = float(os.getenv("FX_VAR_THRESHOLD", "100000"))  # $100k
IR_DV01_THRESHOLD = float(os.getenv("IR_DV01_THRESHOLD", "50000"))  # $50k
MARKET_SHOCK_THRESHOLD = float(os.getenv("MARKET_SHOCK_THRESHOLD", "2.0"))  # 2%


async def get_rabbitmq_connection():
    """Create RabbitMQ connection."""
    return await aio_pika.connect_robust(
        f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"
    )


async def invoke_foundry_agent(agent_task: str, context: Dict) -> Dict:
    """
    Invoke a Foundry agent via API.
    
    Args:
        agent_task: Description of the task for the agent
        context: Context data (contracts, market data, risk results, etc.)
    
    Returns:
        Agent response
    """
    print(f"[Agent Invocation] Task: {agent_task}")
    
    payload = {
        "task": agent_task,
        "context": context,
        "timestamp": datetime.utcnow().isoformat(),
        "mcp_endpoints": {
            "contracts": MCP_CONTRACTS_URL,
            "risk": MCP_RISK_URL,
            "market": MCP_MARKET_URL,
        }
    }
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(
                FOUNDRY_AGENT_ENDPOINT,
                json=payload,
                headers={
                    "Authorization": f"Bearer {FOUNDRY_API_KEY}",
                    "Content-Type": "application/json",
                }
            )
            response.raise_for_status()
            result = response.json()
            print(f"[Agent Response] Status: {result.get('status', 'unknown')}")
            return result
        except Exception as e:
            print(f"[Agent Error] Failed to invoke agent: {e}")
            return {"status": "error", "error": str(e)}


async def handle_risk_result(result_data: Dict):
    """
    Handle completed risk calculation results.
    Checks for threshold breaches and invokes agent if needed.
    """
    job_id = result_data["job_id"]
    status = result_data["status"]
    contract_id = result_data["contract_id"]
    
    print(f"[Risk Result] Job {job_id} for contract {contract_id}: {status}")
    
    if status != "succeeded":
        return
    
    result = result_data.get("result", {})
    
    # Check for threshold breaches
    breach_detected = False
    breach_details = []
    
    if "var" in result:
        var_value = result["var"]
        if var_value > FX_VAR_THRESHOLD:
            breach_detected = True
            breach_details.append(f"FX VaR ${var_value:,.2f} exceeds threshold ${FX_VAR_THRESHOLD:,.2f}")
    
    if "dv01" in result:
        dv01_value = abs(result["dv01"])
        if dv01_value > IR_DV01_THRESHOLD:
            breach_detected = True
            breach_details.append(f"IR DV01 ${dv01_value:,.2f} exceeds threshold ${IR_DV01_THRESHOLD:,.2f}")
    
    if breach_detected:
        print(f"[Threshold Breach] Invoking agent for contract {contract_id}")
        
        await invoke_foundry_agent(
            agent_task="threshold_breach_analysis",
            context={
                "contract_id": contract_id,
                "risk_result": result,
                "breach_details": breach_details,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )


async def detect_market_shock(market_data: Dict):
    """
    Detect significant market movements.
    Invokes agent for portfolio-wide risk reassessment.
    """
    # Check for shocks in market data
    shocks = []
    
    for pair, data in market_data.items():
        if pair == "as_of":
            continue
        
        # Simulate shock detection (in production, compare to previous snapshot)
        # For now, we'll check if volatility spikes or if spot moves significantly
        volatility = data.get("volatility", 0)
        if volatility > 0.15:  # 15% volatility threshold
            shocks.append({
                "currency_pair": pair,
                "volatility": volatility,
                "type": "volatility_spike"
            })
    
    if shocks:
        print(f"[Market Shock] Detected {len(shocks)} market anomalies")
        
        await invoke_foundry_agent(
            agent_task="market_shock_assessment",
            context={
                "shocks": shocks,
                "market_snapshot": market_data,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )


async def run_portfolio_scan():
    """
    Scheduled task: Run comprehensive portfolio risk scan.
    Invoked by cron scheduler.
    """
    print(f"[Portfolio Scan] Starting scheduled scan at {datetime.utcnow().isoformat()}")
    
    await invoke_foundry_agent(
        agent_task="daily_portfolio_risk_scan",
        context={
            "scan_type": "comprehensive",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


async def consume_risk_results():
    """
    Consume risk results from RabbitMQ and handle breaches.
    """
    connection = await get_rabbitmq_connection()
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)
        
        # Declare exchange and queue
        exchange = await channel.declare_exchange(
            "risk.exchange", aio_pika.ExchangeType.DIRECT, durable=True
        )
        
        queue = await channel.declare_queue("risk.results.orchestrator", durable=True)
        await queue.bind(exchange, routing_key="risk.result")
        
        print("[Event Detector] Listening for risk results...")
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    result_data = json.loads(message.body.decode())
                    await handle_risk_result(result_data)


async def monitor_market_events():
    """
    Periodic task: Monitor market for significant events.
    """
    while True:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{MCP_MARKET_URL}/market_snapshot")
                if response.status_code == 200:
                    market_data = response.json()
                    await detect_market_shock(market_data)
        except Exception as e:
            print(f"[Market Monitor] Error: {e}")
        
        # Check every 5 minutes
        await asyncio.sleep(300)


def setup_scheduler():
    """
    Setup cron-based scheduled tasks.
    """
    scheduler = AsyncIOScheduler()
    
    # Daily portfolio scan at 8 AM UTC
    scheduler.add_job(
        run_portfolio_scan,
        CronTrigger(hour=8, minute=0),
        id="daily_portfolio_scan",
        name="Daily Portfolio Risk Scan",
        replace_existing=True,
    )
    
    # Intraday scans every 4 hours
    scheduler.add_job(
        run_portfolio_scan,
        CronTrigger(hour="*/4"),
        id="intraday_portfolio_scan",
        name="Intraday Portfolio Scan",
        replace_existing=True,
    )
    
    scheduler.start()
    print("[Scheduler] Cron jobs configured:")
    print("  - Daily scan: 8:00 AM UTC")
    print("  - Intraday scans: Every 4 hours")
    
    return scheduler


async def main():
    """
    Main orchestrator loop.
    """
    print("=" * 60)
    print("Agent Orchestrator Starting")
    print("=" * 60)
    print(f"Foundry Agent Endpoint: {FOUNDRY_AGENT_ENDPOINT}")
    print(f"MCP Contracts: {MCP_CONTRACTS_URL}")
    print(f"MCP Risk: {MCP_RISK_URL}")
    print(f"MCP Market: {MCP_MARKET_URL}")
    print("=" * 60)
    
    # Setup scheduler for cron-based tasks
    scheduler = setup_scheduler()
    
    # Start background tasks
    tasks = [
        asyncio.create_task(consume_risk_results()),
        asyncio.create_task(monitor_market_events()),
    ]
    
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n[Orchestrator] Shutting down...")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
