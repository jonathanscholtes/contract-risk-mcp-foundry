"""MCP Contracts Server - contract registry and risk memos."""

import sys
from pathlib import Path

# Add shared contracts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))

from datetime import date, datetime
from typing import Dict, List, Optional
import os
from urllib.parse import quote_plus
from mcp.server.fastmcp import FastMCP
from contracts import Contract, ContractType, CurrencyPair
from prometheus_client import Counter, Gauge, start_http_server
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

# Initialize FastMCP server
mcp = FastMCP(
    name="contracts",
    host="0.0.0.0",
    port=80,
    stateless_http=True,
)

# Prometheus metrics
contracts_queried_total = Counter(
    'contracts_queried_total',
    'Total number of contract queries',
    ['query_type']
)
risk_memos_written_total = Counter(
    'risk_memos_written_total',
    'Total number of risk memos written',
    ['contract_id', 'breach_alert']
)
contracts_in_registry = Gauge(
    'contracts_in_registry',
    'Current number of contracts in registry',
    ['contract_type']
)

# MongoDB configuration
MONGODB_CONNECTION_STRING = os.getenv("MONGODB_CONNECTION_STRING", "")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "contracts_db")
MONGODB_CONTRACTS_COLLECTION = os.getenv("MONGODB_CONTRACTS_COLLECTION", "contracts")
MONGODB_MEMOS_COLLECTION = os.getenv("MONGODB_MEMOS_COLLECTION", "risk_memos")

# Initialize MongoDB client
mongo_client = None
contracts_collection = None
memos_collection = None

def update_contract_counts():
    """Update Prometheus metrics for contract counts by type."""
    if mongodb_enabled and contracts_collection is not None:
        try:
            # Count by contract type - use actual enum values
            fx_count = contracts_collection.count_documents({"contract_type": "fx_forward"})
            ir_count = contracts_collection.count_documents({"contract_type": "interest_rate_swap"})
            
            contracts_in_registry.labels(contract_type='FX').set(fx_count)
            contracts_in_registry.labels(contract_type='IR').set(ir_count)
        except PyMongoError as e:
            print(f"Error updating contract counts: {e}")
    else:
        # In-memory fallback
        fx_count = sum(1 for c in contract_store.values() if c.contract_type == ContractType.FX_FORWARD)
        ir_count = sum(1 for c in contract_store.values() if c.contract_type == ContractType.IRS)
        
        contracts_in_registry.labels(contract_type='FX').set(fx_count)
        contracts_in_registry.labels(contract_type='IR').set(ir_count)

def init_mongodb():
    """Initialize MongoDB connection and collections."""
    global mongo_client, contracts_collection, memos_collection
    
    if not MONGODB_CONNECTION_STRING:
        print("WARNING: MONGODB_CONNECTION_STRING not set. Using in-memory storage.")
        return False
    
    try:
        mongo_client = MongoClient(MONGODB_CONNECTION_STRING)
        db = mongo_client[MONGODB_DATABASE]
        contracts_collection = db[MONGODB_CONTRACTS_COLLECTION]
        memos_collection = db[MONGODB_MEMOS_COLLECTION]
        
        # Create indexes
        contracts_collection.create_index("contract_id", unique=True)
        memos_collection.create_index("contract_id")
        memos_collection.create_index("created_at")
        
        # Test connection
        mongo_client.admin.command('ping')
        print(f"Successfully connected to MongoDB: {MONGODB_DATABASE}")
        return True
    except PyMongoError as e:
        print(f"Failed to connect to MongoDB: {e}")
        print("Falling back to in-memory storage.")
        return False

# In-memory fallback storage
contract_store: Dict[str, Contract] = {}
memo_store: Dict[str, List[Dict]] = {}  # contract_id -> list of memos


# Seed some sample contracts
def seed_contracts():
    """Seed sample contracts for testing."""
    import random
    from datetime import timedelta
    sample_contracts = []
    num_fx = 15
    num_irs = 10
    fx_counterparties = ["ABC Bank", "XYZ Corp", "DEF Financial", "GHI Capital", "JKL Partners"]
    irs_counterparties = ["MNO Bank", "PQR Corp", "STU Financial", "VWX Capital", "YZA Partners"]
    fx_pairs = list(CurrencyPair)
    today = date.today()
    # Generate FX Forwards
    for i in range(1, num_fx + 1):
        pair = random.choice(fx_pairs)
        notional_base = random.uniform(100_000, 10_000_000)
        strike = round(random.uniform(1.05, 1.30), 4)
        notional_quote = round(notional_base * strike, 2)
        trade_date = today - timedelta(days=random.randint(0, 365))
        maturity_date = trade_date + timedelta(days=random.randint(30, 365))
        sample_contracts.append(Contract(
            contract_id=f"ctr-fx-{i:03}",
            contract_type=ContractType.FX_FORWARD,
            counterparty=random.choice(fx_counterparties),
            currency_pair=pair,
            notional_base=notional_base,
            notional_quote=notional_quote,
            strike_rate=strike,
            trade_date=trade_date,
            maturity_date=maturity_date,
        ))
    # Generate IRS
    for i in range(1, num_irs + 1):
        notional = random.uniform(1_000_000, 50_000_000)
        fixed_rate = round(random.uniform(0.01, 0.07), 4)
        trade_date = today - timedelta(days=random.randint(0, 365))
        maturity_date = trade_date + timedelta(days=random.randint(365, 365*10))
        sample_contracts.append(Contract(
            contract_id=f"ctr-irs-{i:03}",
            contract_type=ContractType.IRS,
            counterparty=random.choice(irs_counterparties),
            fixed_rate=fixed_rate,
            notional=notional,
            currency="USD",
            trade_date=trade_date,
            maturity_date=maturity_date,
        ))
    
    if contracts_collection is not None:
        # Using MongoDB - check if already seeded
        existing_count = contracts_collection.count_documents({})
        if existing_count > 0:
            print(f"Database already contains {existing_count} contracts. Skipping seed.")
            update_contract_counts()
            return
        
        # Insert sample contracts into MongoDB
        for contract in sample_contracts:
            try:
                contract_dict = contract.model_dump(mode="json")
                contracts_collection.insert_one(contract_dict)
                print(f"Seeded contract: {contract.contract_id}")
            except DuplicateKeyError:
                print(f"Contract {contract.contract_id} already exists, skipping.")
        
        # Update registry size metric
        update_contract_counts()
        print(f"Successfully seeded {len(sample_contracts)} contracts to MongoDB")
    else:
        # Using in-memory storage
        for contract in sample_contracts:
            contract_store[contract.contract_id] = contract
        
        # Update registry size metric
        update_contract_counts()
        print(f"Seeded {len(sample_contracts)} contracts to in-memory storage")


# Initialize MongoDB and seed on startup
mongodb_enabled = init_mongodb()
seed_contracts()


@mcp.tool()
async def search_contracts(
    contract_type: str = "",
    counterparty: str = "",
    currency_pair: str = "",
) -> Dict:
    """
    Search for contracts by various criteria. Use empty string to skip a filter.
    
    Args:
        contract_type: Filter by contract type (fx_forward, irs, etc.). Empty string for no filter.
        counterparty: Filter by counterparty name (case-insensitive partial match). Empty string for no filter.
        currency_pair: Filter by currency pair. Empty string for no filter.
    
    Returns:
        Dictionary with list of matching contracts
    """
    results = []
    
    if contracts_collection is not None:
        # Using MongoDB
        query = {}
        if contract_type:
            query["contract_type"] = contract_type
        if counterparty:
            query["counterparty"] = {"$regex": counterparty, "$options": "i"}
        if currency_pair:
            query["currency_pair"] = currency_pair
        
        cursor = contracts_collection.find(query)
        for doc in cursor:
            # Remove MongoDB's _id field
            doc.pop("_id", None)
            results.append(doc)
    else:
        # Using in-memory storage
        for contract in contract_store.values():
            # Apply filters (empty string means no filter)
            if contract_type and contract.contract_type != contract_type:
                continue
            if counterparty and counterparty.lower() not in contract.counterparty.lower():
                continue
            if currency_pair and contract.currency_pair != currency_pair:
                continue
            
            results.append(contract.model_dump(mode="json"))
    
    # Track query
    contracts_queried_total.labels(query_type='search').inc()
    
    return {
        "contracts": results,
        "count": len(results),
    }


@mcp.tool()
async def get_contract(contract_id: str) -> Dict:
    """
    Get a specific contract by ID.
    
    Args:
        contract_id: Contract identifier
    
    Returns:
        Contract details or error
    """
    if contracts_collection is not None:
        # Using MongoDB
        contract_doc = contracts_collection.find_one({"contract_id": contract_id})
        if not contract_doc:
            return {
                "error": f"Contract {contract_id} not found",
            }
        
        # Remove MongoDB's _id field
        contract_doc.pop("_id", None)
        contracts_queried_total.labels(query_type='get').inc()
        return contract_doc
    else:
        # Using in-memory storage
        if contract_id not in contract_store:
            return {
                "error": f"Contract {contract_id} not found",
            }
        
        contracts_queried_total.labels(query_type='get').inc()
        contract = contract_store[contract_id]
        return contract.model_dump(mode="json")


@mcp.tool()
async def create_contract(
    contract_id: str,
    contract_type: str,
    counterparty: str,
    trade_date: str,
    maturity_date: str,
    currency_pair: str = "",
    notional_base: float = 0.0,
    notional_quote: float = 0.0,
    strike_rate: float = 0.0,
    fixed_rate: float = 0.0,
    notional: float = 0.0,
    currency: str = "",
) -> Dict:
    """
    Create a new contract. Use empty strings or 0.0 for unused fields.
    
    Args:
        contract_id: Unique contract identifier
        contract_type: Type of contract (fx_forward, irs, etc.)
        counterparty: Counterparty name
        trade_date: Trade date (YYYY-MM-DD)
        maturity_date: Maturity date (YYYY-MM-DD)
        currency_pair: Currency pair (for FX contracts). Empty string if not applicable.
        notional_base: Notional in base currency (for FX). 0.0 if not applicable.
        notional_quote: Notional in quote currency (for FX). 0.0 if not applicable.
        strike_rate: Strike rate (for FX). 0.0 if not applicable.
        fixed_rate: Fixed rate (for IRS). 0.0 if not applicable.
        notional: Notional (for IRS). 0.0 if not applicable.
        currency: Currency (for IRS). Empty string if not applicable.
    
    Returns:
        Created contract details or error
    """
    try:
        contract = Contract(
            contract_id=contract_id,
            contract_type=ContractType(contract_type),
            counterparty=counterparty,
            currency_pair=CurrencyPair(currency_pair) if currency_pair else None,
            notional_base=notional_base if notional_base else None,
            notional_quote=notional_quote if notional_quote else None,
            strike_rate=strike_rate if strike_rate else None,
            fixed_rate=fixed_rate if fixed_rate else None,
            notional=notional if notional else None,
            currency=currency if currency else None,
            trade_date=date.fromisoformat(trade_date),
            maturity_date=date.fromisoformat(maturity_date),
        )
        
        if contracts_collection is not None:
            # Using MongoDB
            try:
                contract_dict = contract.model_dump(mode="json")
                contracts_collection.insert_one(contract_dict)
                update_contract_counts()
                
                # Remove _id for response
                contract_dict.pop("_id", None)
                
                return {
                    "message": "Contract created successfully",
                    "contract": contract_dict,
                }
            except DuplicateKeyError:
                return {
                    "error": f"Contract {contract_id} already exists",
                }
        else:
            # Using in-memory storage
            if contract_id in contract_store:
                return {
                    "error": f"Contract {contract_id} already exists",
                }
            
            contract_store[contract_id] = contract
            update_contract_counts()
            
            return {
                "message": "Contract created successfully",
                "contract": contract.model_dump(mode="json"),
            }
    except Exception as e:
        return {
            "error": f"Failed to create contract: {str(e)}",
        }


@mcp.tool()
async def write_risk_memo(
    contract_id: str,
    memo_title: str,
    memo_content: str,
    breach_alert: bool = False,
) -> Dict:
    """
    Write a risk memo for a contract.
    
    Args:
        contract_id: Contract identifier
        memo_title: Title of the memo
        memo_content: Full memo content
        breach_alert: Whether this memo contains a breach alert
    
    Returns:
        Confirmation or error
    """
    # Check if contract exists
    if contracts_collection is not None:
        # Using MongoDB
        contract_exists = contracts_collection.find_one({"contract_id": contract_id})
        if not contract_exists:
            return {
                "error": f"Contract {contract_id} not found",
            }
        
        # Count existing memos for this contract
        memo_count = memos_collection.count_documents({"contract_id": contract_id})
        
        memo = {
            "memo_id": f"memo-{contract_id}-{memo_count + 1}",
            "contract_id": contract_id,
            "title": memo_title,
            "content": memo_content,
            "breach_alert": breach_alert,
            "created_at": datetime.utcnow().isoformat(),
        }
        
        memos_collection.insert_one(memo)
        
        # Update contract's last risk memo date
        contracts_collection.update_one(
            {"contract_id": contract_id},
            {"$set": {"last_risk_memo_date": date.today().isoformat()}}
        )
        
        # Remove _id for response
        memo.pop("_id", None)
    else:
        # Using in-memory storage
        if contract_id not in contract_store:
            return {
                "error": f"Contract {contract_id} not found",
            }
        
        memo = {
            "memo_id": f"memo-{contract_id}-{len(memo_store.get(contract_id, [])) + 1}",
            "contract_id": contract_id,
            "title": memo_title,
            "content": memo_content,
            "breach_alert": breach_alert,
            "created_at": datetime.utcnow().isoformat(),
        }
        
        if contract_id not in memo_store:
            memo_store[contract_id] = []
        
        memo_store[contract_id].append(memo)
        
        # Update contract's last risk memo date
        contract_store[contract_id].last_risk_memo_date = date.today()
    
    # Track memo written
    risk_memos_written_total.labels(
        contract_id=contract_id,
        breach_alert=str(breach_alert).lower()
    ).inc()
    
    return {
        "message": "Risk memo written successfully",
        "memo": memo,
    }


@mcp.tool()
async def get_risk_memos(contract_id: str) -> Dict:
    """
    Get all risk memos for a contract.
    
    Args:
        contract_id: Contract identifier
    
    Returns:
        List of memos or error
    """
    # Check if contract exists
    if contracts_collection is not None:
        # Using MongoDB
        contract_exists = contracts_collection.find_one({"contract_id": contract_id})
        if not contract_exists:
            return {
                "error": f"Contract {contract_id} not found",
            }
        
        # Get all memos for this contract
        cursor = memos_collection.find({"contract_id": contract_id}).sort("created_at", -1)
        memos = []
        for doc in cursor:
            doc.pop("_id", None)
            memos.append(doc)
    else:
        # Using in-memory storage
        if contract_id not in contract_store:
            return {
                "error": f"Contract {contract_id} not found",
            }
        
        memos = memo_store.get(contract_id, [])
    
    return {
        "contract_id": contract_id,
        "memos": memos,
        "count": len(memos),
    }


@mcp.tool()
async def list_all_contracts() -> Dict:
    """
    List all contracts in the system.
    
    Returns:
        Dictionary with list of all contracts
    """
    if contracts_collection is not None:
        # Using MongoDB
        cursor = contracts_collection.find({})
        contracts = []
        for doc in cursor:
            doc.pop("_id", None)
            contracts.append(doc)
    else:
        # Using in-memory storage
        contracts = [contract.model_dump(mode="json") for contract in contract_store.values()]
    
    contracts_queried_total.labels(query_type='list_all').inc()
    
    return {
        "contracts": contracts,
        "count": len(contracts),
    }


if __name__ == "__main__":
    # Start Prometheus metrics server on port 9090
    start_http_server(9090)
    
    # Run the MCP server
    mcp.run(transport="streamable-http")
