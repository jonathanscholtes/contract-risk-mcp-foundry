"""Risk Worker - consumes risk jobs from RabbitMQ and computes results."""

import sys
from pathlib import Path

# Add shared contracts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Optional
import aio_pika
import numpy as np
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# Prometheus metrics
risk_calculations_total = Counter(
    'risk_calculations_total',
    'Total number of risk calculations',
    ['job_type', 'status']
)
risk_calculation_duration = Histogram(
    'risk_calculation_duration_seconds',
    'Duration of risk calculations',
    ['job_type']
)
pending_jobs = Gauge(
    'pending_jobs',
    'Number of pending risk jobs'
)
risk_var_value = Gauge(
    'risk_var_value',
    'Current VaR value for contracts',
    ['contract_id']
)
risk_dv01_value = Gauge(
    'risk_dv01_value',
    'Current DV01 value for contracts',
    ['contract_id']
)

# RabbitMQ configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

# MongoDB configuration
MONGODB_CONNECTION_STRING = os.getenv("MONGODB_CONNECTION_STRING", "")
MONGODB_CONTRACTS_DB = os.getenv("MONGODB_CONTRACTS_DB", "contracts_db")
MONGODB_MARKET_DB = os.getenv("MONGODB_MARKET_DB", "market_db")
MONGODB_RISK_DB = os.getenv("MONGODB_RISK_DB", "risk_db")
MONGODB_CONTRACTS_COLLECTION = os.getenv("MONGODB_CONTRACTS_COLLECTION", "contracts")
MONGODB_MARKET_COLLECTION = os.getenv("MONGODB_MARKET_COLLECTION", "market_data")
MONGODB_JOBS_COLLECTION = os.getenv("MONGODB_JOBS_COLLECTION", "jobs")

# MongoDB clients
mongo_client: Optional[MongoClient] = None
contracts_collection = None
market_collection = None
jobs_collection = None


def init_mongodb():
    """Initialize MongoDB connection."""
    global mongo_client, contracts_collection, market_collection, jobs_collection
    
    if not MONGODB_CONNECTION_STRING:
        print("WARNING: MONGODB_CONNECTION_STRING not set. Using fallback values.")
        return False
    
    try:
        mongo_client = MongoClient(MONGODB_CONNECTION_STRING)
        
        # Contracts database
        contracts_db = mongo_client[MONGODB_CONTRACTS_DB]
        contracts_collection = contracts_db[MONGODB_CONTRACTS_COLLECTION]
        
        # Market database
        market_db = mongo_client[MONGODB_MARKET_DB]
        market_collection = market_db[MONGODB_MARKET_COLLECTION]
        
        # Risk database
        risk_db = mongo_client[MONGODB_RISK_DB]
        jobs_collection = risk_db[MONGODB_JOBS_COLLECTION]
        
        # Test connection
        mongo_client.admin.command('ping')
        print(f"Successfully connected to MongoDB")
        return True
    except PyMongoError as e:
        print(f"Failed to connect to MongoDB: {e}")
        print("Will use fallback values for calculations.")
        return False


async def get_rabbitmq_connection():
    """Create RabbitMQ connection."""
    return await aio_pika.connect_robust(
        f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"
    )


def compute_fx_var(params: Dict, contract_data: Dict) -> Dict:
    """
    Compute FX VaR using Monte Carlo simulation.
    
    Uses market data from MongoDB for volatility.
    """
    horizon_days = params.get("horizon_days", 1)
    confidence = params.get("confidence", 0.99)
    sims = params.get("sims", 20000)
    
    # Get contract details
    notional = contract_data.get("notional_base", 1000000.0)
    currency_pair = contract_data.get("currency_pair")
    
    # Fetch volatility from market data
    volatility = 0.10  # Default fallback
    if market_collection is not None and currency_pair:
        try:
            market_doc = market_collection.find_one({"currency_pair": currency_pair})
            if market_doc and "volatility" in market_doc:
                volatility = market_doc["volatility"]
                print(f"Using volatility {volatility} for {currency_pair} from market data")
            else:
                print(f"No market data found for {currency_pair}, using default volatility {volatility}")
        except PyMongoError as e:
            print(f"Error fetching market data: {e}, using default volatility {volatility}")
    else:
        print(f"Market collection not available, using default volatility {volatility}")
    
    # Scale to horizon
    horizon_vol = volatility * np.sqrt(horizon_days / 252)
    
    # Generate random returns
    returns = np.random.normal(0, horizon_vol, sims)
    
    # Compute P&L
    pnl = notional * returns
    
    # VaR is the negative of the appropriate percentile
    var_percentile = (1 - confidence) * 100
    var = -np.percentile(pnl, var_percentile)
    
    return {
        "var": round(float(var), 2),
        "confidence": confidence,
        "horizon_days": horizon_days,
        "simulations": sims,
        "volatility_used": volatility,
        "currency_pair": currency_pair,
        "as_of": datetime.utcnow().isoformat(),
    }


def compute_ir_dv01(params: Dict, contract_data: Dict) -> Dict:
    """
    Compute IR DV01 (dollar value of 1bp move).
    
    Simplified implementation for MVP.
    """
    shift_bps = params.get("shift_bps", 1.0)
    
    # Get contract details
    notional = contract_data.get("notional", 5000000.0)
    fixed_rate = contract_data.get("fixed_rate", 0.045)
    
    # Simple approximation: DV01 = notional * duration * 0.0001
    # Assume 5-year duration for simplicity
    duration = 5.0
    dv01 = notional * duration * (shift_bps / 10000)
    
    return {
        "dv01": round(float(dv01), 2),
        "shift_bps": shift_bps,
        "currency": contract_data.get("currency", "USD"),
        "as_of": datetime.utcnow().isoformat(),
    }


async def process_job(job_data: Dict) -> Dict:
    """
    Process a risk calculation job.
    """
    job_id = job_data["job_id"]
    job_type = job_data["job_type"]
    contract_id = job_data["contract_id"]
    params = job_data["params"]
    
    # Track job as pending
    pending_jobs.inc()
    
    print(f"Processing job {job_id} ({job_type}) for contract {contract_id}")
    
    # Track calculation start time
    start_time = datetime.utcnow()
    
    # Fetch contract data from MongoDB
    contract_data = None
    if contracts_collection is not None:
        try:
            contract_data = contracts_collection.find_one({"contract_id": contract_id})
            if contract_data:
                print(f"Loaded contract {contract_id} from database")
                # Remove MongoDB _id field
                contract_data.pop("_id", None)
            else:
                print(f"Contract {contract_id} not found in database")
        except PyMongoError as e:
            print(f"Error fetching contract from MongoDB: {e}")
    
    # Fallback to mock data if not found
    if contract_data is None:
        print(f"Using fallback data for contract {contract_id}")
        contract_data = {
            "contract_id": contract_id,
            "notional_base": 1000000.0,
            "notional": 5000000.0,
            "fixed_rate": 0.045,
            "currency": "USD",
        }
    
    # Simulate some processing time
    await asyncio.sleep(2)
    
    try:
        if job_type == "fx_var":
            result = compute_fx_var(params, contract_data)
            # Store VaR value in gauge
            risk_var_value.labels(contract_id=contract_id).set(result['var'])
        elif job_type == "ir_dv01":
            result = compute_ir_dv01(params, contract_data)
            # Store DV01 value in gauge
            risk_dv01_value.labels(contract_id=contract_id).set(result['dv01'])
        else:
            raise ValueError(f"Unknown job type: {job_type}")
        
        # Track successful calculation
        pending_jobs.dec()
        duration = (datetime.utcnow() - start_time).total_seconds()
        risk_calculation_duration.labels(job_type=job_type).observe(duration)
        risk_calculations_total.labels(job_type=job_type, status='success').inc()
        
        return {
            "job_id": job_id,
            "job_type": job_type,
            "status": "succeeded",
            "contract_id": contract_id,
            "result": result,
        }
    except Exception as e:
        # Track failed calculation
        duration = (datetime.utcnow() - start_time).total_seconds()
        risk_calculation_duration.labels(job_type=job_type).observe(duration)
        pending_jobs.dec()
        risk_calculations_total.labels(job_type=job_type, status='failed').inc()
        
        return {
            "job_id": job_id,
            "job_type": job_type,
            "status": "failed",
            "contract_id": contract_id,
            "error": str(e),
        }


async def publish_result(channel, result_data: Dict) -> None:
    """Publish a result to the risk.results queue and update MongoDB."""
    exchange = await channel.get_exchange("risk.exchange")
    
    message = aio_pika.Message(
        body=json.dumps(result_data).encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    
    await exchange.publish(message, routing_key="risk.result")
    print(f"Published result for job {result_data['job_id']}")
    
    # Update MongoDB with result
    job_id = result_data["job_id"]
    update_data = {
        "status": result_data["status"],
        "result": result_data.get("result"),
        "error": result_data.get("error"),
        "completed_at": datetime.utcnow().isoformat(),
    }
    
    if jobs_collection is not None:
        try:
            jobs_collection.update_one(
                {"job_id": job_id},
                {"$set": update_data}
            )
            print(f"Updated MongoDB for job {job_id}")
        except PyMongoError as e:
            print(f"Error updating job in MongoDB: {e}")


async def consume_jobs():
    """Consume jobs from the risk.jobs queue."""
    print("Starting risk worker...")
    
    connection = await get_rabbitmq_connection()
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        
        # Declare exchange and queues
        exchange = await channel.declare_exchange(
            "risk.exchange", aio_pika.ExchangeType.DIRECT, durable=True
        )
        
        job_queue = await channel.declare_queue("risk.jobs", durable=True)
        await job_queue.bind(exchange, routing_key="risk.job")
        
        print("Waiting for jobs...")
        
        async with job_queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    job_data = json.loads(message.body.decode())
                    
                    # Process the job
                    result = await process_job(job_data)
                    
                    # Publish result
                    await publish_result(channel, result)


if __name__ == "__main__":
    # Initialize MongoDB
    init_mongodb()
    
    # Start Prometheus metrics server on port 9090
    start_http_server(9090)
    print("Prometheus metrics server started on port 9090")
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(consume_jobs())
