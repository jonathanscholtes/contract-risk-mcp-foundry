"""MCP Risk Server - submits risk jobs and retrieves results."""

import sys
from pathlib import Path

# Add shared contracts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))

import os
import uuid
from datetime import datetime
from typing import Dict, Optional
from mcp.server.fastmcp import FastMCP
import aio_pika
import json
import asyncio

# Initialize FastMCP server
mcp = FastMCP("risk")

# RabbitMQ configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

# In-memory job status store (in production, use a database)
job_store: Dict[str, Dict] = {}


async def get_rabbitmq_connection():
    """Create RabbitMQ connection."""
    return await aio_pika.connect_robust(
        f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"
    )


async def publish_job(job_data: Dict) -> None:
    """Publish a job to the risk.jobs queue."""
    connection = await get_rabbitmq_connection()
    async with connection:
        channel = await connection.channel()
        
        # Declare exchange and queue
        exchange = await channel.declare_exchange(
            "risk.exchange", aio_pika.ExchangeType.DIRECT, durable=True
        )
        
        queue = await channel.declare_queue("risk.jobs", durable=True)
        await queue.bind(exchange, routing_key="risk.job")
        
        # Publish message
        message = aio_pika.Message(
            body=json.dumps(job_data).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        
        await exchange.publish(message, routing_key="risk.job")


@mcp.tool()
async def run_fx_var(
    contract_id: str,
    horizon_days: int = 1,
    confidence: float = 0.99,
    simulations: int = 20000,
) -> Dict[str, str]:
    """
    Submit an FX VaR calculation job.
    
    Args:
        contract_id: Contract identifier
        horizon_days: Risk horizon in days (default: 1)
        confidence: Confidence level (default: 0.99)
        simulations: Number of Monte Carlo simulations (default: 20000)
    
    Returns:
        Dictionary with job_id and status
    """
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    idempotency_key = f"{contract_id}|fx_var|{datetime.utcnow().date()}"
    
    job_data = {
        "job_id": job_id,
        "job_type": "fx_var",
        "contract_id": contract_id,
        "params": {
            "horizon_days": horizon_days,
            "confidence": confidence,
            "sims": simulations,
        },
        "idempotency_key": idempotency_key,
    }
    
    # Store job status
    job_store[job_id] = {
        "status": "pending",
        "submitted_at": datetime.utcnow().isoformat(),
        "job_data": job_data,
    }
    
    # Publish to RabbitMQ
    await publish_job(job_data)
    
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Job submitted successfully",
    }


@mcp.tool()
async def run_ir_dv01(
    contract_id: str,
    shift_bps: float = 1.0,
) -> Dict[str, str]:
    """
    Submit an IR DV01 calculation job.
    
    Args:
        contract_id: Contract identifier
        shift_bps: Rate shift in basis points (default: 1.0)
    
    Returns:
        Dictionary with job_id and status
    """
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    idempotency_key = f"{contract_id}|ir_dv01|{datetime.utcnow().date()}"
    
    job_data = {
        "job_id": job_id,
        "job_type": "ir_dv01",
        "contract_id": contract_id,
        "params": {
            "shift_bps": shift_bps,
        },
        "idempotency_key": idempotency_key,
    }
    
    # Store job status
    job_store[job_id] = {
        "status": "pending",
        "submitted_at": datetime.utcnow().isoformat(),
        "job_data": job_data,
    }
    
    # Publish to RabbitMQ
    await publish_job(job_data)
    
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Job submitted successfully",
    }


@mcp.tool()
def get_risk_result(job_id: str) -> Dict:
    """
    Get the result of a risk calculation job.
    
    Args:
        job_id: Job identifier
    
    Returns:
        Dictionary with job status and result (if complete)
    """
    if job_id not in job_store:
        return {
            "error": f"Job {job_id} not found",
            "status": "unknown",
        }
    
    job_info = job_store[job_id]
    
    return {
        "job_id": job_id,
        "status": job_info["status"],
        "submitted_at": job_info["submitted_at"],
        "result": job_info.get("result"),
        "error": job_info.get("error"),
        "completed_at": job_info.get("completed_at"),
    }


@mcp.tool()
def list_jobs(status: Optional[str] = None) -> Dict[str, list]:
    """
    List all jobs, optionally filtered by status.
    
    Args:
        status: Optional status filter (pending, processing, succeeded, failed)
    
    Returns:
        Dictionary with list of jobs
    """
    jobs = []
    for job_id, job_info in job_store.items():
        if status is None or job_info["status"] == status:
            jobs.append({
                "job_id": job_id,
                "status": job_info["status"],
                "contract_id": job_info["job_data"]["contract_id"],
                "job_type": job_info["job_data"]["job_type"],
                "submitted_at": job_info["submitted_at"],
            })
    
    return {
        "jobs": jobs,
        "count": len(jobs),
    }


# Background task to consume results from RabbitMQ
async def consume_results():
    """Consume job results from the risk.results queue."""
    connection = await get_rabbitmq_connection()
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)
        
        # Declare exchange and queue
        exchange = await channel.declare_exchange(
            "risk.exchange", aio_pika.ExchangeType.DIRECT, durable=True
        )
        
        queue = await channel.declare_queue("risk.results", durable=True)
        await queue.bind(exchange, routing_key="risk.result")
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    result_data = json.loads(message.body.decode())
                    job_id = result_data["job_id"]
                    
                    if job_id in job_store:
                        job_store[job_id]["status"] = result_data["status"]
                        job_store[job_id]["result"] = result_data.get("result")
                        job_store[job_id]["error"] = result_data.get("error")
                        job_store[job_id]["completed_at"] = datetime.utcnow().isoformat()


if __name__ == "__main__":
    # Start background result consumer
    loop = asyncio.get_event_loop()
    loop.create_task(consume_results())
    
    # Run the MCP server
    mcp.run()
