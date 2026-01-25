"""Risk Worker - consumes risk jobs from RabbitMQ and computes results."""

import sys
from pathlib import Path

# Add shared contracts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))

import os
import json
import asyncio
from datetime import datetime
from typing import Dict
import aio_pika
import numpy as np
from prometheus_client import Counter, Histogram, Gauge, start_http_server

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


async def get_rabbitmq_connection():
    """Create RabbitMQ connection."""
    return await aio_pika.connect_robust(
        f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"
    )


def compute_fx_var(params: Dict, contract_data: Dict) -> Dict:
    """
    Compute FX VaR using Monte Carlo simulation.
    
    Simplified implementation for MVP.
    """
    horizon_days = params.get("horizon_days", 1)
    confidence = params.get("confidence", 0.99)
    sims = params.get("sims", 20000)
    
    # Get contract details
    notional = contract_data.get("notional_base", 1000000.0)
    
    # Assume 10% annualized volatility for simplicity
    volatility = 0.10
    
    # Scale to horizon
    horizon_vol = volatility * np.sqrt(horizon_days / 252)
    
    # Generate random returns
    np.random.seed(42)  # For reproducibility in demo
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
    
    print(f"Processing job {job_id} ({job_type}) for contract {contract_id}")
    
    # Track calculation start time
    start_time = datetime.utcnow()
    
    # Simulate some processing time
    await asyncio.sleep(2)
    
    # Mock contract data (in production, fetch from contract service)
    contract_data = {
        "contract_id": contract_id,
        "notional_base": 1000000.0,
        "notional": 5000000.0,
        "fixed_rate": 0.045,
        "currency": "USD",
    }
    
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
        duration = (datetime.utcnow() - start_time).total_seconds()
        risk_calculation_duration.labels(job_type=job_type).observe(duration)
        risk_calculations_total.labels(job_type=job_type, status='success').inc()
        
        return {
            "job_id": job_id,
            "status": "succeeded",
            "contract_id": contract_id,
            "result": result,
        }
    except Exception as e:
        # Track failed calculation
        duration = (datetime.utcnow() - start_time).total_seconds()
        risk_calculation_duration.labels(job_type=job_type).observe(duration)
        risk_calculations_total.labels(job_type=job_type, status='failed').inc()
        
        return {
            "job_id": job_id,
            "status": "failed",
            "contract_id": contract_id,
            "error": str(e),
        }


async def publish_result(channel, result_data: Dict) -> None:
    """Publish a result to the risk.results queue."""
    exchange = await channel.get_exchange("risk.exchange")
    
    message = aio_pika.Message(
        body=json.dumps(result_data).encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    
    await exchange.publish(message, routing_key="risk.result")
    print(f"Published result for job {result_data['job_id']}")


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
        
        result_queue = await channel.declare_queue("risk.results", durable=True)
        await result_queue.bind(exchange, routing_key="risk.result")
        
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
    # Start Prometheus metrics server on port 9090
    start_http_server(9090)
    print("Prometheus metrics server started on port 9090")
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(consume_jobs())
