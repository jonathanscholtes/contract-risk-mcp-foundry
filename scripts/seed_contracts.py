"""Seed sample contracts into the contracts service."""

import requests
from datetime import date, timedelta

# Contract service URL
CONTRACTS_URL = "http://localhost:8001"


def create_contract(contract_data):
    """Create a contract via the API."""
    response = requests.post(f"{CONTRACTS_URL}/contracts", json=contract_data)
    if response.status_code == 200:
        print(f"✓ Created contract {contract_data['contract_id']}")
    else:
        print(f"✗ Failed to create {contract_data['contract_id']}: {response.text}")


def main():
    """Seed sample contracts."""
    print("Seeding sample contracts...")
    
    contracts = [
        {
            "contract_id": "ctr-fx-001",
            "contract_type": "fx_forward",
            "counterparty": "ABC Bank",
            "currency_pair": "EURUSD",
            "notional_base": 1000000.0,
            "notional_quote": 1085000.0,
            "strike_rate": 1.085,
            "trade_date": str(date.today() - timedelta(days=30)),
            "maturity_date": str(date.today() + timedelta(days=150)),
        },
        {
            "contract_id": "ctr-fx-002",
            "contract_type": "fx_forward",
            "counterparty": "XYZ Corp",
            "currency_pair": "GBPUSD",
            "notional_base": 500000.0,
            "notional_quote": 632500.0,
            "strike_rate": 1.265,
            "trade_date": str(date.today() - timedelta(days=20)),
            "maturity_date": str(date.today() + timedelta(days=140)),
        },
        {
            "contract_id": "ctr-irs-001",
            "contract_type": "irs",
            "counterparty": "DEF Financial",
            "fixed_rate": 0.045,
            "notional": 5000000.0,
            "currency": "USD",
            "trade_date": str(date.today() - timedelta(days=60)),
            "maturity_date": str(date.today() + timedelta(days=1800)),
        },
        {
            "contract_id": "ctr-fx-003",
            "contract_type": "fx_forward",
            "counterparty": "Global Traders",
            "currency_pair": "USDJPY",
            "notional_base": 2000000.0,
            "notional_quote": 297000000.0,
            "strike_rate": 148.50,
            "trade_date": str(date.today() - timedelta(days=10)),
            "maturity_date": str(date.today() + timedelta(days=90)),
        },
    ]
    
    for contract in contracts:
        create_contract(contract)
    
    print(f"\n✓ Seeded {len(contracts)} contracts")


if __name__ == "__main__":
    main()
