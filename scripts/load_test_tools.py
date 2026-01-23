"""Load test MCP tool endpoints."""

import requests
import time
import concurrent.futures
from datetime import datetime

# Service URLs
CONTRACTS_URL = "http://localhost:8001"
RISK_URL = "http://localhost:8002"
MARKET_URL = "http://localhost:8003"


def call_search_contracts():
    """Test search_contracts endpoint."""
    response = requests.get(f"{CONTRACTS_URL}/search")
    return response.status_code == 200


def call_run_fx_var(contract_id):
    """Test run_fx_var endpoint."""
    response = requests.post(
        f"{RISK_URL}/run_fx_var",
        json={
            "contract_id": contract_id,
            "horizon_days": 1,
            "confidence": 0.99,
            "simulations": 20000,
        }
    )
    return response.status_code == 200


def call_get_fx_spot(currency_pair):
    """Test get_fx_spot endpoint."""
    response = requests.get(f"{MARKET_URL}/fx_spot/{currency_pair}")
    return response.status_code == 200


def run_load_test(func, name, iterations=100, workers=10):
    """Run a load test."""
    print(f"\n=== Testing {name} ===")
    print(f"Iterations: {iterations}, Workers: {workers}")
    
    start_time = time.time()
    success_count = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        for _ in range(iterations):
            if name == "search_contracts":
                future = executor.submit(call_search_contracts)
            elif name == "run_fx_var":
                future = executor.submit(call_run_fx_var, "ctr-fx-001")
            elif name == "get_fx_spot":
                future = executor.submit(call_get_fx_spot, "EURUSD")
            futures.append(future)
        
        for future in concurrent.futures.as_completed(futures):
            if future.result():
                success_count += 1
    
    elapsed_time = time.time() - start_time
    success_rate = (success_count / iterations) * 100
    throughput = iterations / elapsed_time
    
    print(f"Elapsed time: {elapsed_time:.2f}s")
    print(f"Success rate: {success_rate:.1f}%")
    print(f"Throughput: {throughput:.1f} req/s")


def main():
    """Run load tests."""
    print("MCP Tool Load Testing")
    print(f"Started at: {datetime.now()}\n")
    
    # Test each endpoint
    run_load_test(call_search_contracts, "search_contracts", iterations=100, workers=10)
    run_load_test(call_get_fx_spot, "get_fx_spot", iterations=100, workers=10)
    run_load_test(call_run_fx_var, "run_fx_var", iterations=50, workers=5)
    
    print("\n=== Load testing complete ===")
    print("Check Grafana dashboards for queue depth and worker scaling")


if __name__ == "__main__":
    main()
