"""MCP Contracts Server - contract registry and risk memos."""

import sys
from pathlib import Path

# Add shared contracts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))

from datetime import date, datetime
from typing import Dict, List, Optional
import os
from mcp.server.fastmcp import FastMCP
from contracts import Contract, ContractType, CurrencyPair

# Initialize FastMCP server
mcp = FastMCP(
    name="contracts",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
)

# In-memory contract store (in production, use a database)
contract_store: Dict[str, Contract] = {}
memo_store: Dict[str, List[Dict]] = {}  # contract_id -> list of memos


# Seed some sample contracts
def seed_contracts():
    """Seed sample contracts for testing."""
    sample_contracts = [
        Contract(
            contract_id="ctr-001",
            contract_type=ContractType.FX_FORWARD,
            counterparty="ABC Bank",
            currency_pair=CurrencyPair.EURUSD,
            notional_base=1000000.0,
            notional_quote=1085000.0,
            strike_rate=1.085,
            trade_date=date(2026, 1, 15),
            maturity_date=date(2026, 7, 15),
        ),
        Contract(
            contract_id="ctr-002",
            contract_type=ContractType.FX_FORWARD,
            counterparty="XYZ Corp",
            currency_pair=CurrencyPair.GBPUSD,
            notional_base=500000.0,
            notional_quote=632500.0,
            strike_rate=1.265,
            trade_date=date(2026, 1, 10),
            maturity_date=date(2026, 6, 10),
        ),
        Contract(
            contract_id="ctr-003",
            contract_type=ContractType.IRS,
            counterparty="DEF Financial",
            fixed_rate=0.045,
            notional=5000000.0,
            currency="USD",
            trade_date=date(2025, 12, 1),
            maturity_date=date(2030, 12, 1),
        ),
    ]
    
    for contract in sample_contracts:
        contract_store[contract.contract_id] = contract


# Seed on startup
seed_contracts()


@mcp.tool()
def search_contracts(
    contract_type: Optional[str] = None,
    counterparty: Optional[str] = None,
    currency_pair: Optional[str] = None,
) -> Dict[str, List[Dict]]:
    """
    Search for contracts by various criteria.
    
    Args:
        contract_type: Filter by contract type (fx_forward, irs, etc.)
        counterparty: Filter by counterparty name (case-insensitive partial match)
        currency_pair: Filter by currency pair
    
    Returns:
        Dictionary with list of matching contracts
    """
    results = []
    
    for contract in contract_store.values():
        # Apply filters
        if contract_type and contract.contract_type != contract_type:
            continue
        if counterparty and counterparty.lower() not in contract.counterparty.lower():
            continue
        if currency_pair and contract.currency_pair != currency_pair:
            continue
        
        results.append(contract.model_dump(mode="json"))
    
    return {
        "contracts": results,
        "count": len(results),
    }


@mcp.tool()
def get_contract(contract_id: str) -> Dict:
    """
    Get a specific contract by ID.
    
    Args:
        contract_id: Contract identifier
    
    Returns:
        Contract details or error
    """
    if contract_id not in contract_store:
        return {
            "error": f"Contract {contract_id} not found",
        }
    
    contract = contract_store[contract_id]
    return contract.model_dump(mode="json")


@mcp.tool()
def create_contract(
    contract_id: str,
    contract_type: str,
    counterparty: str,
    trade_date: str,
    maturity_date: str,
    currency_pair: Optional[str] = None,
    notional_base: Optional[float] = None,
    notional_quote: Optional[float] = None,
    strike_rate: Optional[float] = None,
    fixed_rate: Optional[float] = None,
    notional: Optional[float] = None,
    currency: Optional[str] = None,
) -> Dict:
    """
    Create a new contract.
    
    Args:
        contract_id: Unique contract identifier
        contract_type: Type of contract (fx_forward, irs, etc.)
        counterparty: Counterparty name
        trade_date: Trade date (YYYY-MM-DD)
        maturity_date: Maturity date (YYYY-MM-DD)
        currency_pair: Currency pair (for FX contracts)
        notional_base: Notional in base currency (for FX)
        notional_quote: Notional in quote currency (for FX)
        strike_rate: Strike rate (for FX)
        fixed_rate: Fixed rate (for IRS)
        notional: Notional (for IRS)
        currency: Currency (for IRS)
    
    Returns:
        Created contract details or error
    """
    if contract_id in contract_store:
        return {
            "error": f"Contract {contract_id} already exists",
        }
    
    try:
        contract = Contract(
            contract_id=contract_id,
            contract_type=ContractType(contract_type),
            counterparty=counterparty,
            currency_pair=CurrencyPair(currency_pair) if currency_pair else None,
            notional_base=notional_base,
            notional_quote=notional_quote,
            strike_rate=strike_rate,
            fixed_rate=fixed_rate,
            notional=notional,
            currency=currency,
            trade_date=date.fromisoformat(trade_date),
            maturity_date=date.fromisoformat(maturity_date),
        )
        
        contract_store[contract_id] = contract
        
        return {
            "message": "Contract created successfully",
            "contract": contract.model_dump(mode="json"),
        }
    except Exception as e:
        return {
            "error": f"Failed to create contract: {str(e)}",
        }


@mcp.tool()
def write_risk_memo(
    contract_id: str,
    memo_title: str,
    memo_content: str,
    risk_metrics: Optional[Dict] = None,
    breach_alert: bool = False,
) -> Dict:
    """
    Write a risk memo for a contract.
    
    Args:
        contract_id: Contract identifier
        memo_title: Title of the memo
        memo_content: Full memo content
        risk_metrics: Optional dict of risk metrics (VaR, DV01, etc.)
        breach_alert: Whether this memo contains a breach alert
    
    Returns:
        Confirmation or error
    """
    if contract_id not in contract_store:
        return {
            "error": f"Contract {contract_id} not found",
        }
    
    memo = {
        "memo_id": f"memo-{len(memo_store.get(contract_id, []))+ 1}",
        "contract_id": contract_id,
        "title": memo_title,
        "content": memo_content,
        "risk_metrics": risk_metrics or {},
        "breach_alert": breach_alert,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    if contract_id not in memo_store:
        memo_store[contract_id] = []
    
    memo_store[contract_id].append(memo)
    
    # Update contract's last risk memo date
    contract_store[contract_id].last_risk_memo_date = date.today()
    
    return {
        "message": "Risk memo written successfully",
        "memo": memo,
    }


@mcp.tool()
def get_risk_memos(contract_id: str) -> Dict[str, List[Dict]]:
    """
    Get all risk memos for a contract.
    
    Args:
        contract_id: Contract identifier
    
    Returns:
        List of memos or error
    """
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
def list_all_contracts() -> Dict[str, List[Dict]]:
    """
    List all contracts in the system.
    
    Returns:
        Dictionary with list of all contracts
    """
    contracts = [contract.model_dump(mode="json") for contract in contract_store.values()]
    
    return {
        "contracts": contracts,
        "count": len(contracts),
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run(transport="streamable-http")
