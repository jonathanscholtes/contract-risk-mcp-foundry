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
from azure.identity.aio import DefaultAzureCredential
from azure.ai.projects.aio import AIProjectClient

# Configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

# Azure AI Project configuration
AZURE_AI_PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]  # Required environment variable

# Agent names for different tasks
PORTFOLIO_SCAN_AGENT = os.getenv("PORTFOLIO_SCAN_AGENT", "PortfolioScanAnalyst")
MARKET_SHOCK_AGENT = os.getenv("MARKET_SHOCK_AGENT", "MarketShockAnalyst")
THRESHOLD_BREACH_AGENT = os.getenv("THRESHOLD_BREACH_AGENT", "ThresholdBreachAnalyst")

# Thresholds
FX_VAR_THRESHOLD = float(os.getenv("FX_VAR_THRESHOLD", "100000"))  # $100k
IR_DV01_THRESHOLD = float(os.getenv("IR_DV01_THRESHOLD", "50000"))  # $50k
MARKET_SHOCK_THRESHOLD = float(os.getenv("MARKET_SHOCK_THRESHOLD", "2.0"))  # 2%


async def get_rabbitmq_connection():
    """Create RabbitMQ connection."""
    return await aio_pika.connect_robust(
        f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"
    )


async def invoke_foundry_agent(agent_name: str, agent_task: str, context: Dict) -> Dict:
    """
    Invoke a Foundry agent using Azure AI Projects SDK.
    Agent is pre-configured with MCP tools at deployment time.
    
    Args:
        agent_name: Name of the agent to invoke
        agent_task: Description of the task for the agent
        context: Context data (contracts, market data, risk results, etc.)
    
    Returns:
        Agent response
    """
    print(f"[Agent Invocation] Agent: {agent_name}, Task: {agent_task}")
    
    # Format context as user message
    # Note: Agent already has MCP tools configured, no need to pass URLs
    user_message = f"""{agent_task}

Context:
{json.dumps(context, indent=2)}
"""
    
    try:
        async with DefaultAzureCredential() as credential:
            async with AIProjectClient(
                endpoint=AZURE_AI_PROJECT_ENDPOINT,
                credential=credential
            ) as project_client:
                
                # Get the agent by name
                agent = await project_client.agents.get(agent_name=agent_name)
                print(f"[Agent] Retrieved {agent.name} (id: {agent.id})")
                
                async with project_client.get_openai_client() as openai_client:
                    # Create a new conversation for this task
                    conversation = await openai_client.conversations.create()
                    print(f"[Conversation] Created conversation (id: {conversation.id})")
                    
                    # Add user message to conversation
                    await openai_client.conversations.items.create(
                        conversation_id=conversation.id,
                        items=[{
                            "type": "message",
                            "role": "user",
                            "content": user_message
                        }]
                    )
                    
                    # Get response from agent
                    response = await openai_client.responses.create(
                        conversation=conversation.id,
                        extra_body={
                            "agent": {
                                "name": agent.name,
                                "type": "agent_reference"
                            }
                        },
                        input=""
                    )
                    
                    print(f"[Agent Response] Received response from agent")
                    return {
                        "status": "success",
                        "output": response.output_text,
                        "conversation_id": conversation.id,
                        "agent_id": agent.id
                    }
    
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
            agent_name=THRESHOLD_BREACH_AGENT,
            agent_task="Analyze this threshold breach and provide recommendations",
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
            agent_name=MARKET_SHOCK_AGENT,
            agent_task="Assess the impact of these market shocks on the portfolio",
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
        agent_name=PORTFOLIO_SCAN_AGENT,
        agent_task="Run a comprehensive portfolio risk scan",
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
    print(f"Azure AI Project: {AZURE_AI_PROJECT_ENDPOINT}")
    print(f"Portfolio Scan Agent: {PORTFOLIO_SCAN_AGENT}")
    print(f"Market Shock Agent: {MARKET_SHOCK_AGENT}")
    print(f"Threshold Breach Agent: {THRESHOLD_BREACH_AGENT}")
    print("Note: Agents are pre-configured with MCP tools")
    print("=" * 60)
    
    # Setup scheduler for cron-based tasks
    scheduler = setup_scheduler()
    scheduler.start()
    print("[Scheduler] Started - tasks scheduled")
    
    # Run an immediate portfolio scan on startup for testing
    print("[Startup] Running initial portfolio scan...")
    try:
        await run_portfolio_scan()
        print("[Startup] Initial portfolio scan completed")
    except Exception as e:
        print(f"[Startup] Error during initial scan: {e}")
    
    # Start background tasks
    tasks = [
        asyncio.create_task(consume_risk_results()),
    ]
    
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n[Orchestrator] Shutting down...")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
