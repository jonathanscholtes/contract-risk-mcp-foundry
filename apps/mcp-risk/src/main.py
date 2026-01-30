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
    Submit an FX Value-at-Risk (VaR) calculation job. USE ONLY FOR FX CONTRACTS.
    
    This tool calculates the maximum potential loss in an FX position under normal market conditions.
    
    Use this tool ONLY for:
    - FX forward contracts (contract_type='fx_forward')
    - Currency exposure analysis
    
    DO NOT use for:
    - Interest Rate Swap (IRS) contracts → use run_ir_dv01() instead
    - Other derivative types
    
    Args:
        contract_id: FX contract identifier (must be FX forward contract type)
        horizon_days: Risk calculation horizon (1=overnight, 10=10 days). Default: 1
        confidence: Confidence level (0.99=99%, 0.95=95%). Default: 0.99
        simulations: Monte Carlo simulation count. Default: 20000 (higher=more accurate but slower)
    
    Returns:
        Dictionary with:
        - job_id: Unique identifier to track calculation (use with get_risk_result)
        - status: 'pending' (job queued for processing)
        - message: 'Job submitted successfully'
    
    Workflow:
        1. Submit job: job_result = run_fx_var(contract_id='ctr-fx-001')
        2. Poll result: get_risk_result(job_id=job_result['job_id']) until status != 'pending'
        3. Use VaR value in your analysis
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
    Submit an Interest Rate DV01 (Dollar Value of 1 basis point) calculation job. USE ONLY FOR IRS CONTRACTS.
    
    This tool calculates the price sensitivity of an interest rate swap to 1bp (0.01%) rate movement.
    
    Use this tool ONLY for:
    - Interest Rate Swap (IRS) contracts (contract_type='interest_rate_swap')
    - IR curve exposure analysis
    
    DO NOT use for:
    - FX forward contracts → use run_fx_var() instead
    - Other derivative types
    
    Args:
        contract_id: IRS contract identifier (must be interest_rate_swap contract type)
        shift_bps: Interest rate shift for sensitivity in basis points (default: 1.0 bps = 0.01%)
    
    Returns:
        Dictionary with:
        - job_id: Unique identifier to track calculation (use with get_risk_result)
        - status: 'pending' (job queued for processing)
        - message: 'Job submitted successfully'
    
    Workflow:
        1. Submit job: job_result = run_ir_dv01(contract_id='ctr-irs-001')
        2. Poll result: get_risk_result(job_id=job_result['job_id']) until status != 'pending'
        3. Use DV01 value to assess rate sensitivity
    
    Interpretation:
        - DV01 = $X means position loses/gains $X if rates move 1bp
        - Higher DV01 = more rate sensitive (more hedge needed)
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
    Poll for the result of a submitted risk calculation job.
    
    Use this tool to:
    - Check if a risk calculation (run_fx_var or run_ir_dv01) has completed
    - Retrieve the computed risk metrics (VaR or DV01 value)
    - Detect failures and get error messages
    
    Args:
        job_id: Job identifier returned from run_fx_var() or run_ir_dv01()
    
    Returns:
        Dictionary with:
        - status: 'pending' (still calculating), 'succeeded' (result ready), 'failed' (error)
        - result: Risk metrics (VaR or DV01 dict) if status='succeeded'
        - error: Error message if status='failed'
        - completed_at: Timestamp when calculation finished (if complete)
    
    Polling Pattern:
        1. Submit job: result = run_fx_var(contract_id)
        2. Poll loop: 
           while True:
             status = get_risk_result(result['job_id'])
             if status['status'] in ['succeeded', 'failed']:
               break
             sleep(2)
        3. Check result['status'] - use result if succeeded, handle error if failed
    
    Notes:
        - Use exponential backoff or wait 2-5s between polls
        - Timeout after 5+ minutes of 'pending' status (job may have failed)
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
    List all risk calculation jobs, optionally filtered by status.
    
    Use this tool to:
    - Monitor portfolio risk calculation progress
    - Identify failed jobs that need troubleshooting
    - Get overview of pending/completed calculations
    
    Args:
        status: Filter by job status. Options:
               - '' (empty string): All jobs
               - 'pending': Jobs waiting to be processed
               - 'processing': Jobs currently running
               - 'succeeded': Completed successfully
               - 'failed': Jobs that encountered errors
    
    Returns:
        Dictionary with:
        - jobs: List of job summaries with job_id, status, contract_id, job_type, submitted_at
        - count: Total number of jobs matching filter
    
    Examples:
        - list_jobs(status='') → all jobs
        - list_jobs(status='failed') → only failed jobs (check for errors)
        - list_jobs(status='pending') → jobs still processing
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





if __name__ == "__main__":
    # Initialize MongoDB
    init_mongodb()
    
    # Start Prometheus metrics server on port 9090
    start_http_server(9090)
    
    # Run the MCP server (blocking)
    # Note: Result consumption and persistence is handled by the risk-worker
    mcp.run(transport="streamable-http")
