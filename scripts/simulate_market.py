"""Simulate market data updates."""

import requests
import time
import random
import os

# Market service URL - use environment variable or localhost
MARKET_URL = os.getenv("MCP_MARKET_URL", "http://localhost:8003")


def simulate_shock(currency_pair, shock_pct):
    """Simulate a market shock."""
    print(f"Simulating {shock_pct:+.2f}% shock on {currency_pair}...")
    response = requests.post(
        f"{MARKET_URL}/simulate_shock",
        json={
            "currency_pair": currency_pair,
            "shock_pct": shock_pct,
        }
    )
    if response.status_code == 200:
        result = response.json()
        print(f"  Original: {result['original_spot']}")
        print(f"  Shocked:  {result['shocked_spot']}")
    else:
        print(f"  Error: {response.text}")


def main():
    """Run market simulation scenarios."""
    print("Market Simulation Scenarios\n")
    
    # Scenario 1: FX Shock Day
    print("=== Scenario 1: FX Shock Day ===")
    simulate_shock("EURUSD", -3.0)
    time.sleep(1)
    simulate_shock("GBPUSD", -2.5)
    time.sleep(1)
    
    # Scenario 2: Rate Jump (would affect IR products)
    print("\n=== Scenario 2: Interest Rate Jump ===")
    print("Simulating +75 bps parallel shift...")
    print("(This would be implemented via a separate rates shock API)")
    
    # Scenario 3: Normal volatility
    print("\n=== Scenario 3: Normal Market Movement ===")
    for _ in range(5):
        pair = random.choice(["EURUSD", "GBPUSD", "USDJPY"])
        shock = random.uniform(-0.5, 0.5)
        simulate_shock(pair, shock)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
