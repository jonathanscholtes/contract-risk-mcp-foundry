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
import random
import aio_pika
import httpx
from datetime import datetime, time
from typing import Dict, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from azure.identity.aio import DefaultAzureCredential
from azure.ai.projects.aio import AIProjectClient
from alpha_vantage.foreignexchange import ForeignExchange
from pymongo import MongoClient
from urllib.parse import quote_plus

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


# Market data configuration
MONGODB_CONNECTION_STRING = os.getenv("MONGODB_CONNECTION_STRING", "")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "market_db")
MONGODB_MARKET_COLLECTION = os.getenv("MONGODB_MARKET_COLLECTION", "market_data")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
USE_FAKE_MARKET_DATA = os.getenv("USE_FAKE_MARKET_DATA", "true").lower() == "true" or ALPHA_VANTAGE_API_KEY == "demo"

# Currency pairs to monitor
MARKET_CURRENCY_PAIRS = [
    ("EUR", "USD"),
    ("GBP", "USD"),
    ("USD", "JPY"),
    ("AUD", "USD"),
    ("USD", "CAD"),
    ("USD", "CHF"),
    ("NZD", "USD"),
    ("EUR", "GBP"),
    ("EUR", "JPY"),
    ("GBP", "JPY"),
]


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
    
    max_retries = 5
    delay = 2  # seconds
    for attempt in range(1, max_retries + 1):
        try:
            async with DefaultAzureCredential() as credential:
                async with AIProjectClient(
                    endpoint=AZURE_AI_PROJECT_ENDPOINT,
                    credential=credential
                ) as project_client:
                    # Retrieve the agent by name
                    agent = await project_client.agents.get(agent_name=agent_name)
                    print(f"[Agent] Retrieved {agent.name} (id: {agent.id}, version: {agent.versions.latest.version})")
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
            # Check for 429 Too Many Requests
            if hasattr(e, 'status_code') and e.status_code == 429:
                print(f"[Agent Error] 429 Too Many Requests. Attempt {attempt}/{max_retries}. Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
                continue
            # Azure OpenAI/HTTPX error with 429 in message
            if '429' in str(e) or 'too_many_requests' in str(e):
                print(f"[Agent Error] 429 Too Many Requests. Attempt {attempt}/{max_retries}. Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
                delay *= 2
                continue
            print(f"[Agent Error] Failed to invoke agent: {e}")
            return {"status": "error", "error": str(e)}
    print(f"[Agent Error] Exceeded max retries for agent: {agent_name}")
    return {"status": "error", "error": "Too Many Requests: exceeded retry attempts"}



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


async def update_market_data():
    """
    Scheduled task: Fetch FX market data and update MongoDB.
    Runs every 15 minutes to keep market data current.
    """
    if not MONGODB_CONNECTION_STRING:
        print("[Market Data] MongoDB connection string not set, skipping update")
        return
    
    print(f"[Market Data] Starting market data update at {datetime.utcnow().isoformat()}")
    
    try:
        # URL encode credentials if needed
        connection_string = MONGODB_CONNECTION_STRING
        if "://" in connection_string and "@" in connection_string:
            protocol, rest = connection_string.split("://", 1)
            if "@" in rest:
                creds, host_part = rest.split("@", 1)
                if ":" in creds:
                    username, password = creds.split(":", 1)
                    encoded_creds = f"{quote_plus(username)}:{quote_plus(password)}"
                    connection_string = f"{protocol}://{encoded_creds}@{host_part}"

        mongo_client = MongoClient(connection_string)
        db = mongo_client[MONGODB_DATABASE]
        market_collection = db[MONGODB_MARKET_COLLECTION]

        updated_count = 0
        for base, quote in MARKET_CURRENCY_PAIRS:
            pair = f"{base}{quote}"
            try:
                if USE_FAKE_MARKET_DATA:
                    # Generate fake spot and volatility
                    spot = round(random.uniform(0.8, 1.3), 4) if quote == "USD" else round(random.uniform(90, 160), 2)
                    volatility = round(random.uniform(0.07, 0.12), 4)
                else:
                    fx = ForeignExchange(key=ALPHA_VANTAGE_API_KEY, output_format='json')
                    data, _ = fx.get_currency_exchange_rate(from_currency=base, to_currency=quote)
                    spot = float(data["5. Exchange Rate"])
                    volatility = round(random.uniform(0.07, 0.12), 4)

                doc = {
                    "currency_pair": pair,
                    "spot": spot,
                    "volatility": volatility,
                    "as_of": datetime.utcnow().isoformat(),
                }

                market_collection.update_one(
                    {"currency_pair": pair},
                    {"$set": doc},
                    upsert=True
                )

                print(f"[Market Data] Updated {pair}: spot={spot}, vol={volatility}")
                updated_count += 1

            except Exception as e:
                print(f"[Market Data] Error updating {pair}: {e}")

        print(f"[Market Data] Successfully updated {updated_count}/{len(MARKET_CURRENCY_PAIRS)} currency pairs")

    except Exception as e:
        print(f"[Market Data] MongoDB connection failed: {e}")


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
    
    # Market data updates every 15 minutes
    scheduler.add_job(
        update_market_data,
        CronTrigger(minute="*/15"),
        id="market_data_update",
        name="Market Data Update",
        replace_existing=True,
    )
    
    print("[Scheduler] Cron jobs configured:")
    print("  - Daily scan: 8:00 AM UTC")
    print("  - Intraday scans: Every 4 hours")
    print("  - Market data updates: Every 15 minutes")
    
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
    
    # Run initial market data update on startup
    print("[Startup] Running initial market data update...")
    try:
        await update_market_data()
        print("[Startup] Initial market data update completed")
    except Exception as e:
        print(f"[Startup] Error during market data update: {e}")
    
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
