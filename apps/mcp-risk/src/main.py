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
from prometheus_client import Counter, Gauge, start_http_server
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# Initialize FastMCP server
mcp = FastMCP(
    name="risk",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
    stateless_http=True,
)

# Prometheus metrics
jobs_submitted_total = Counter(
    'jobs_submitted_total',
    'Total number of risk jobs submitted',
    ['job_type']
)
jobs_completed_total = Counter(
    'jobs_completed_total',
    'Total number of risk jobs completed',
    ['job_type', 'status']
)
pending_jobs = Gauge(
    'pending_jobs',
    'Number of pending risk jobs'
)

# RabbitMQ configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

# MongoDB configuration
MONGODB_CONNECTION_STRING = os.getenv("MONGODB_CONNECTION_STRING", "")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "risk_db")
MONGODB_JOBS_COLLECTION = os.getenv("MONGODB_JOBS_COLLECTION", "jobs")

# Initialize MongoDB client
mongo_client = None
jobs_collection = None
mongodb_enabled = False

# In-memory job status store (fallback if MongoDB is not available)
job_store: Dict[str, Dict] = {}


def init_mongodb():
    """Initialize MongoDB connection and collection."""
    global mongo_client, jobs_collection, mongodb_enabled
    
    if not MONGODB_CONNECTION_STRING:
        print("WARNING: MONGODB_CONNECTION_STRING not set. Using in-memory storage.")
        return False
    
    try:
        mongo_client = MongoClient(MONGODB_CONNECTION_STRING)
        db = mongo_client[MONGODB_DATABASE]
        jobs_collection = db[MONGODB_JOBS_COLLECTION]
        
        # Create indexes
        jobs_collection.create_index("job_id", unique=True)
        jobs_collection.create_index("status")
        jobs_collection.create_index("submitted_at")
        
        # Test connection
        mongo_client.admin.command('ping')
        print(f"Successfully connected to MongoDB: {MONGODB_DATABASE}")
        mongodb_enabled = True
        return True
    except PyMongoError as e:
        print(f"Failed to connect to MongoDB: {e}")
        print("Falling back to in-memory storage.")
        mongodb_enabled = False
        return False


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
    job_data_with_meta = {
        "job_id": job_id,
        "status": "pending",
        "submitted_at": datetime.utcnow().isoformat(),
        "job_data": job_data,
    }
    
    if mongodb_enabled and jobs_collection is not None:
        try:
            jobs_collection.insert_one(job_data_with_meta.copy())
        except PyMongoError as e:
            print(f"Error storing job in MongoDB: {e}")
            # Fallback to in-memory
            job_store[job_id] = job_data_with_meta
    else:
        job_store[job_id] = job_data_with_meta
    
    # Track metrics
    jobs_submitted_total.labels(job_type='fx_var').inc()
    pending_jobs.inc()
    
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
    job_data_with_meta = {
        "job_id": job_id,
        "status": "pending",
        "submitted_at": datetime.utcnow().isoformat(),
        "job_data": job_data,
    }
    
    if mongodb_enabled and jobs_collection is not None:
        try:
            jobs_collection.insert_one(job_data_with_meta.copy())
        except PyMongoError as e:
            print(f"Error storing job in MongoDB: {e}")
            # Fallback to in-memory
            job_store[job_id] = job_data_with_meta
    else:
        job_store[job_id] = job_data_with_meta
    
    # Track metrics
    jobs_submitted_total.labels(job_type='ir_dv01').inc()
    pending_jobs.inc()
    
    # Publish to RabbitMQ
    await publish_job(job_data)
    
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Job submitted successfully",
    }


@mcp.tool()
async def get_risk_result(job_id: str) -> Dict:
    """
    Get the result of a risk calculation job.
    
    Args:
        job_id: Job identifier
    
    Returns:
        Dictionary with job status and result (if complete)
    """
    job_info = None
    
    # Try MongoDB first
    if mongodb_enabled and jobs_collection is not None:
        try:
            job_info = jobs_collection.find_one({"job_id": job_id}, {"_id": 0})
        except PyMongoError as e:
            print(f"Error retrieving job from MongoDB: {e}")
    
    # Fallback to in-memory
    if job_info is None and job_id in job_store:
        job_info = job_store[job_id]
    
    if job_info is None:
        return {
            "error": f"Job {job_id} not found",
            "status": "unknown",
        }
    
    return {
        "job_id": job_id,
        "status": job_info["status"],
        "submitted_at": job_info["submitted_at"],
        "result": job_info.get("result"),
        "error": job_info.get("error"),
        "completed_at": job_info.get("completed_at"),
    }


@mcp.tool()
async def list_jobs(status: str = "") -> Dict:
    """
    List all jobs, optionally filtered by status. Use empty string for no filter.
    
    Args:
        status: Optional status filter (pending, processing, succeeded, failed). Empty string for all jobs.
    
    Returns:
        Dictionary with list of jobs
    """
    jobs = []
    
    # Try MongoDB first
    if mongodb_enabled and jobs_collection is not None:
        try:
            query = {"status": status} if status else {}
            cursor = jobs_collection.find(query, {"_id": 0})
            
            for job_info in cursor:
                jobs.append({
                    "job_id": job_info["job_id"],
                    "status": job_info["status"],
                    "contract_id": job_info["job_data"]["contract_id"],
                    "job_type": job_info["job_data"]["job_type"],
                    "submitted_at": job_info["submitted_at"],
                })
        except PyMongoError as e:
            print(f"Error listing jobs from MongoDB: {e}")
    
    # Fallback to in-memory or append if MongoDB returned nothing
    if not jobs:
        for job_id, job_info in job_store.items():
            if not status or job_info["status"] == status:
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
                    
                    # Track completion metrics (use result_data, not job_store)
                    job_type = result_data.get("job_type", "unknown")
                    status = result_data["status"]
                    jobs_completed_total.labels(job_type=job_type, status=status).inc()
                    pending_jobs.dec()
                    
                    # Update job in MongoDB
                    update_data = {
                        "status": result_data["status"],
                        "result": result_data.get("result"),
                        "error": result_data.get("error"),
                        "completed_at": datetime.utcnow().isoformat(),
                    }
                    
                    if mongodb_enabled and jobs_collection is not None:
                        try:
                            jobs_collection.update_one(
                                {"job_id": job_id},
                                {"$set": update_data}
                            )
                        except PyMongoError as e:
                            print(f"Error updating job in MongoDB: {e}")
                    
                    # Also update in-memory store if job exists there
                    if job_id in job_store:
                        job_store[job_id].update(update_data)


if __name__ == "__main__":
    # Initialize MongoDB
    init_mongodb()
    
    # Start Prometheus metrics server on port 9090
    start_http_server(9090)
    
    # Start background result consumer
    loop = asyncio.get_event_loop()
    loop.create_task(consume_results())
    
    # Run the MCP server
    mcp.run(transport="streamable-http")
